# task26100477 — 钱包地址解析与批量登记库

纯 Python（仅标准库），支持 Ethereum、Polygon、Bitcoin 主网、Solana。
登记结果持久化在 SQLite，重新打开后规范地址与钱包标识保持不变。

## 能力

```python
from walletlib import WalletRegistry, parse_address, ETHEREUM, BITCOIN

# 1. 单条解析：返回规范地址及所属网络，无效抛 InvalidAddressError
parsed = parse_address(ETHEREUM, "0x5aaeb6053f3e94c9b9a09f33669435e7ef1beaed")
assert parsed.canonical == "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed"

# 2. 批量登记：每批最多 500 条，任一无效则整批不落库
reg = WalletRegistry("wallets.db")
ids = reg.register_batch([
    (ETHEREUM, "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed"),
    (BITCOIN, "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"),
])

# 3. 查询登记结果：返回稳定钱包标识，未登记返回 None
wid = reg.query(ETHEREUM, "0x5AAEB6053F3E94C9B9A09F33669435E7EF1BEAED")
reg.close()
```

## 规则要点

- Ethereum / Polygon：小写 `0x` 前缀 + 40 位十六进制；全小写/全大写直接接受，
  混合大小写须通过 EIP-55（Keccak-256，非 SHA3-256）；规范形式为 EIP-55。
- Bitcoin：P2PKH/P2SH 走 Base58Check（版本 0/5，载荷 20 字节，保留原大小写）；
  见证地址按 BIP173/BIP350（`bc` 前缀、≤90 字符、禁混合大小写、规范为小写；
  v0 仅 20/32 字节且 bech32，v1–v16 为 2–40 字节且 bech32m，尾部填充须为 0–4 位零）。
- Solana：Base58 解码恰为 32 字节（前导零计入），不做曲线点检查，大小写不折叠。
- 合并语义：网络不同必为不同钱包；同网络仅合并解码含义相同的地址
  （Bitcoin 的 P2PKH/P2SH/各见证版本互不合并）。钱包标识由
  `sha256(network + 规范地址)` 派生，天然幂等。

## 测试

```bash
python3 -m unittest discover -s tests
```

- `tests/test_vectors.py`：EIP-55 官方向量、BIP173/BIP350 规范有效/无效向量、
  错误校验和、非零填充、未来见证版本、Solana 前导零等固定向量。
- `tests/test_registry.py`：大小写别名合并、跨链/跨地址种类隔离、整批回滚、
  重复提交幂等、重开库持久化，以及 10 万已登记钱包下 500 条混合批次 < 2s 的性能验收。
