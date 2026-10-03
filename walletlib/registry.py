"""基于 SQLite 的钱包批量登记与查询。"""

import hashlib
import sqlite3

from .address import parse_address
from .errors import BatchTooLargeError

MAX_BATCH_SIZE = 500

_SCHEMA = """
CREATE TABLE IF NOT EXISTS wallets (
    wallet_id TEXT PRIMARY KEY,
    network   TEXT NOT NULL,
    canonical TEXT NOT NULL,
    seq       INTEGER NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_wallets_identity
    ON wallets (network, canonical);
"""


def _wallet_id(network: str, canonical: str) -> str:
    """由 (网络, 规范地址) 派生的稳定钱包标识。"""
    digest = hashlib.sha256(f"{network}\x00{canonical}".encode("utf-8")).hexdigest()
    return "w_" + digest[:32]


class WalletRegistry:
    """同一用户的钱包登记表，持久化在 SQLite 文件中。"""

    def __init__(self, db_path: str) -> None:
        self._conn = sqlite3.connect(db_path)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "WalletRegistry":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _next_seq(self) -> int:
        row = self._conn.execute("SELECT COALESCE(MAX(seq), 0) FROM wallets").fetchone()
        return row[0] + 1

    def register_batch(self, entries: list[tuple[str, str]]) -> list[str]:
        """批量登记 (网络, 地址)，按输入顺序返回钱包标识列表。

        任一条无效则整批不落库。重复项返回已有标识。
        """
        if len(entries) > MAX_BATCH_SIZE:
            raise BatchTooLargeError(f"单批最多 {MAX_BATCH_SIZE} 条")
        # 先全部解析校验，任一失败直接抛错，不产生任何写入
        parsed = [parse_address(network, text) for network, text in entries]
        seq = self._next_seq()
        with self._conn:
            for offset, item in enumerate(parsed):
                self._conn.execute(
                    "INSERT OR IGNORE INTO wallets (wallet_id, network, canonical, seq)"
                    " VALUES (?, ?, ?, ?)",
                    (_wallet_id(item.network, item.canonical),
                     item.network, item.canonical, seq + offset),
                )
        return [_wallet_id(item.network, item.canonical) for item in parsed]

    def query(self, network: str, text: str) -> str | None:
        """查询单条地址对应的钱包标识，未登记返回 None。"""
        item = parse_address(network, text)
        row = self._conn.execute(
            "SELECT wallet_id FROM wallets WHERE network = ? AND canonical = ?",
            (item.network, item.canonical),
        ).fetchone()
        return row[0] if row else None

    def count(self) -> int:
        """已登记钱包总数。"""
        row = self._conn.execute("SELECT COUNT(*) FROM wallets").fetchone()
        return row[0]
