"""基于 SQLite 的钱包批量登记与查询。"""

import sqlite3
import uuid

from .networks import Network, parse_address

_BATCH_LIMIT = 500
# 固定命名空间，保证同一规范化键永远派生同一钱包标识
_NAMESPACE = uuid.UUID("6f1c9e2a-7b3d-4e5f-9a0b-1c2d3e4f5a6b")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS wallets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet_id TEXT NOT NULL UNIQUE,
    key BLOB NOT NULL UNIQUE,
    network TEXT NOT NULL,
    canonical TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
"""


class WalletRegistry:
    """同一个 SQLite 数据库文件上的钱包登记表。"""

    def __init__(self, db_path: str) -> None:
        self._conn = sqlite3.connect(db_path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)

    def _wallet_id_for(self, key: bytes) -> str:
        return "w" + uuid.uuid5(_NAMESPACE, key.hex()).hex

    def register_batch(self, entries: list[tuple[Network, str]]) -> list[str]:
        """批量登记，按输入顺序返回每条对应的钱包标识。

        任一条无效则整批不落库并抛 ValueError。每批最多 500 条。
        重复项与已登记钱包不新增记录，重复提交结果不变。
        """
        if len(entries) > _BATCH_LIMIT:
            raise ValueError(f"每批最多 {_BATCH_LIMIT} 条")
        # 先全部解析：任何一条无效都不会触碰数据库
        parsed = [parse_address(network, address) for network, address in entries]

        result: list[str] = []
        with self._conn:  # 单事务，异常即整体回滚
            for item in parsed:
                row = self._conn.execute(
                    "SELECT wallet_id FROM wallets WHERE key = ?", (item.key,)
                ).fetchone()
                if row is None:
                    wallet_id = self._wallet_id_for(item.key)
                    self._conn.execute(
                        "INSERT INTO wallets (wallet_id, key, network, canonical)"
                        " VALUES (?, ?, ?, ?)",
                        (wallet_id, item.key, item.network.value, item.canonical),
                    )
                else:
                    wallet_id = row[0]
                result.append(wallet_id)
        return result

    def get(self, network: Network, address: str) -> str | None:
        """查询单条地址对应的钱包标识。地址无效抛 ValueError，未登记返回 None。"""
        item = parse_address(network, address)
        row = self._conn.execute(
            "SELECT wallet_id FROM wallets WHERE key = ?", (item.key,)
        ).fetchone()
        return row[0] if row else None

    def count(self) -> int:
        """返回已登记钱包总数。"""
        row = self._conn.execute("SELECT COUNT(*) FROM wallets").fetchone()
        return row[0]

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "WalletRegistry":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
