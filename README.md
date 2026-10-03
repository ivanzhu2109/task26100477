# task26100477

钱包地址解析与批量登记库（纯 Python + SQLite，无第三方依赖）。

## 能力

- **单条解析** `parse_address(network, address)`：返回规范地址及所属网络，无效地址抛 `ValueError`。
- **批量登记** `WalletRegistry.register_batch(entries)`：每批最多 500 条，按输入顺序返回稳定的钱包标识；任一条无效则整批不落库。
- **查询** `WalletRegistry.get(network, address)` / `count()`。

## 支持网络与规则

| 网络 | 规则 | 规范地址 |
|---|---|---|
| Ethereum / Polygon | 小写 `0x` + 40 位 hex；全小写/全大写直接接受，混合大小写须过 EIP-55（Keccak-256，非 SHA3-256） | EIP-55 形式 |
| Bitcoin | P2PKH/P2SH 走 Base58Check（版本 0/5，载荷 20 字节）；见证 v0–v16 走 BIP173/BIP350（前缀 `bc`，≤90 字符，禁混合大小写）；v0 仅 20/32 字节且 Bech32，v1+ 为 2–40 字节且 Bech32m | 传统地址保留原文；见证地址全小写 |
| Solana | Base58 解码恰为 32 字节（前导零计入），不做曲线检查，大小写不折叠 | 保留原文 |

去重语义：网络不同则钱包必不同；同网络内仅解码含义相同才合并（Bitcoin 的 P2PKH / P2SH / 各见证版本互不合并）。

## 用法

```python
from wallet_registry import Network, WalletRegistry, parse_address

parsed = parse_address(Network.ETHEREUM, "0x5aaeb6053f3e94c9b9a09f33669435e7ef1beaed")
print(parsed.canonical)  # 0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed

with WalletRegistry("wallets.db") as reg:
    ids = reg.register_batch([
        (Network.ETHEREUM, "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed"),
        (Network.BITCOIN,  "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"),
        (Network.SOLANA,   "11111111111111111111111111111111"),
    ])
    print(ids, reg.count())
    print(reg.get(Network.ETHEREUM, "0x5AAEB6053F3E94C9B9A09F33669435E7EF1BEAED"))  # 同标识
```

## 测试

```bash
python3 -m pytest tests/ -q
```

- `tests/test_vectors.py`：固定地址向量（EIP-55 官方向量、BIP173/BIP350 有效与无效向量、
  非零填充 / 未来见证版本 / 非法程序长度、Solana 前导零等）。
- `tests/test_registry.py`：大小写别名合并、跨链同文本隔离、Bitcoin 地址种类隔离、
  整批回滚、幂等重投、重开数据库标识不变、10 万钱包下 500 条混合批次性能（<2 秒）。
