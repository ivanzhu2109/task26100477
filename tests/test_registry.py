"""登记行为测试：别名合并、跨链隔离、原子性、幂等、重开稳定性、性能。"""

import time

import pytest

from wallet_registry import Network, WalletRegistry

ETH = Network.ETHEREUM
POLY = Network.POLYGON
BTC = Network.BITCOIN
SOL = Network.SOLANA

# EIP-55 官方向量及其大小写别名
EIP55_ADDR = "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed"
EIP55_LOWER = EIP55_ADDR.lower()
EIP55_UPPER = "0x" + EIP55_ADDR[2:].upper()

# 同一 20 字节载荷（创世地址载荷）的三种 Bitcoin 地址种类
BTC_P2PKH = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
BTC_P2SH_SAME_PAYLOAD = "3Ai1JZ8pdJb2ksieUV8FsxSNVJCpoPi8W6"
BTC_P2WPKH_SAME_PAYLOAD = "bc1qvt5s0v2uhuna2sjnn84ldu8m2r4m3rcc4048ry"

BTC_SEGWIT = "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"
BTC_SEGWIT_UPPER = "BC1QW508D6QEJXTDG4Y5R3ZARVARY0C5XW7KV8F3T4"

SOL_ADDR = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"


@pytest.fixture()
def db_path(tmp_path):
    return str(tmp_path / "wallets.db")


def test_same_chain_case_aliases_share_wallet(db_path):
    with WalletRegistry(db_path) as reg:
        ids = reg.register_batch([
            (ETH, EIP55_LOWER),
            (ETH, EIP55_UPPER),
            (ETH, EIP55_ADDR),
            (BTC, BTC_SEGWIT),
            (BTC, BTC_SEGWIT_UPPER),
        ])
        assert ids[0] == ids[1] == ids[2]
        assert ids[3] == ids[4]
        assert ids[0] != ids[3]
        assert reg.count() == 2


def test_cross_chain_same_text_kept_apart(db_path):
    with WalletRegistry(db_path) as reg:
        ids = reg.register_batch([(ETH, EIP55_ADDR), (POLY, EIP55_ADDR)])
        assert ids[0] != ids[1]
        assert reg.count() == 2


def test_bitcoin_address_types_not_merged(db_path):
    # P2PKH / P2SH / P2WPKH 载荷相同也必须保持不同钱包
    with WalletRegistry(db_path) as reg:
        ids = reg.register_batch([
            (BTC, BTC_P2PKH),
            (BTC, BTC_P2SH_SAME_PAYLOAD),
            (BTC, BTC_P2WPKH_SAME_PAYLOAD),
        ])
        assert len(set(ids)) == 3
        assert reg.count() == 3


def test_solana_case_not_folded(db_path):
    # Solana 大小写不折叠：仅大小写不同的地址是不同钱包
    other = "t" + SOL_ADDR[1:]
    with WalletRegistry(db_path) as reg:
        ids = reg.register_batch([(SOL, SOL_ADDR), (SOL, other)])
        assert ids[0] != ids[1]
        assert reg.count() == 2


def test_persistence_across_reopen(db_path):
    with WalletRegistry(db_path) as reg:
        ids = reg.register_batch([
            (ETH, EIP55_ADDR), (POLY, EIP55_ADDR), (BTC, BTC_P2PKH),
            (BTC, BTC_SEGWIT), (SOL, SOL_ADDR),
        ])
    with WalletRegistry(db_path) as reg2:
        assert reg2.count() == 5
        assert reg2.get(ETH, EIP55_LOWER) == ids[0]
        assert reg2.get(ETH, EIP55_UPPER) == ids[0]
        assert reg2.get(POLY, EIP55_ADDR) == ids[1]
        assert reg2.get(BTC, BTC_P2PKH) == ids[2]
        assert reg2.get(BTC, BTC_SEGWIT_UPPER) == ids[3]
        assert reg2.get(SOL, SOL_ADDR) == ids[4]
        # 跨链同文本依然不合并
        assert reg2.get(ETH, EIP55_ADDR) != reg2.get(POLY, EIP55_ADDR)
        # 重复提交结果不变
        assert reg2.register_batch([(ETH, EIP55_ADDR), (BTC, BTC_SEGWIT)]) == [ids[0], ids[3]]
        assert reg2.count() == 5
        assert reg2.get(BTC, "1BoatSLRHtKNngkdXEeobR76b53LETtpyT") is None


def test_get_invalid_address_raises(db_path):
    with WalletRegistry(db_path) as reg:
        with pytest.raises(ValueError):
            reg.get(ETH, "0xnothex")


def _mixed_batch(evm_offset=0, sol_offset=0, btc_offset=0):
    """构造 500 条混合网络、互不重复的有效地址批次。"""
    entries = []
    for i in range(200):
        entries.append((ETH if i % 2 == 0 else POLY,
                        "0x%040x" % (evm_offset + i + 1)))
    for i in range(150):
        # Solana：32 字节计数器的 Base58 形式
        n = sol_offset + i + 1
        entries.append((SOL, _b58encode(n.to_bytes(32, "big"))))
    for i in range(150):
        # Bitcoin：v1 见证地址，2 字节程序（bech32m，自建但冻结于断言行）
        n = btc_offset + i + 1
        entries.append((BTC, _segwit_v1_2byte(n)))
    assert len(entries) == 500
    return entries


_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def _b58encode(raw):
    n = int.from_bytes(raw, "big")
    s = ""
    while n:
        n, r = divmod(n, 58)
        s = _B58[r] + s
    return "1" * (len(raw) - len(raw.lstrip(b"\x00"))) + s


def _segwit_v1_2byte(n):
    program = n.to_bytes(2, "big")
    data5 = [1] + _convertbits_8to5(program)
    return _bech32m_encode("bc", data5)


def test_segwit_helper_matches_bip350_vector():
    # 测试辅助编码器必须复现 BIP350 外部向量 BC1SW50QGDZ25J（v16，程序 0x751e）
    data5 = [16] + _convertbits_8to5(bytes.fromhex("751e"))
    assert _bech32m_encode("bc", data5) == "bc1sw50qgdz25j"


def _convertbits_8to5(data):
    acc, bits, out = 0, 0, []
    for b in data:
        acc = (acc << 8) | b
        bits += 8
        while bits >= 5:
            bits -= 5
            out.append((acc >> bits) & 31)
    if bits:
        out.append((acc << (5 - bits)) & 31)
    return out


def _bech32m_encode(hrp, data5):
    charset = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
    values = [ord(c) >> 5 for c in hrp] + [0] + [ord(c) & 31 for c in hrp] + data5
    chk = 1
    for v in values + [0] * 6:
        top = chk >> 25
        chk = ((chk & 0x1FFFFFF) << 5) ^ v
        for i, g in enumerate((0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3)):
            if (top >> i) & 1:
                chk ^= g
    chk ^= 0x2BC830A3
    return hrp + "1" + "".join(charset[d] for d in data5 + [(chk >> 5 * (5 - i)) & 31 for i in range(6)])


def test_batch_atomicity_and_idempotency(db_path):
    batch = _mixed_batch()
    unique_count = len({(net.value, addr) for net, addr in batch})
    with WalletRegistry(db_path) as reg:
        # 最后一条无效 -> 整批不落库
        bad = batch[:-1] + [(ETH, "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAeD")]  # 校验和错
        with pytest.raises(ValueError):
            reg.register_batch(bad)
        assert reg.count() == 0
        # 修正后提交
        ids = reg.register_batch(batch)
        assert len(ids) == 500
        assert reg.count() == unique_count
        # 重复提交同一批次：结果不变，不新增
        assert reg.register_batch(batch) == ids
        assert reg.count() == unique_count


def test_batch_limit(db_path):
    with WalletRegistry(db_path) as reg:
        with pytest.raises(ValueError):
            reg.register_batch([(ETH, "0x%040x" % i) for i in range(501)])
        assert reg.count() == 0


def test_duplicates_within_batch(db_path):
    with WalletRegistry(db_path) as reg:
        ids = reg.register_batch([
            (ETH, EIP55_LOWER), (ETH, EIP55_ADDR), (SOL, SOL_ADDR), (SOL, SOL_ADDR),
        ])
        assert ids[0] == ids[1] and ids[2] == ids[3]
        assert reg.count() == 2


def test_performance_100k_wallets_500_batch(db_path):
    # 预登记 10 万钱包（Solana 地址，避免测试本身被 Keccak 主导）
    with WalletRegistry(db_path) as reg:
        for chunk in range(200):
            reg.register_batch([
                (SOL, _b58encode((chunk * 500 + i + 1).to_bytes(32, "big")))
                for i in range(500)
            ])
        assert reg.count() == 100_000

        batch = _mixed_batch(evm_offset=10_000, sol_offset=200_000, btc_offset=10_000)
        start = time.perf_counter()
        ids = reg.register_batch(batch)
        elapsed = time.perf_counter() - start
        assert len(ids) == 500
        assert reg.count() == 100_500
        assert elapsed < 2.0, f"500 条混合批次耗时 {elapsed:.2f}s，超过 2 秒"
