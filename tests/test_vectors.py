"""固定地址向量测试：EIP-55 / Base58Check / BIP173 / BIP350 / Solana。

向量来源：
- EIP-55 提案官方示例；
- BIP173 / BIP350 测试向量及比特币创世地址（Bitcoin Wiki 公开记录）；
- BIP86 测试向量地址（v1 taproot）；
- SPL Token 程序地址等 Solana 公开地址；
- 少量自建向量（非零填充、未来版本、非法长度）均为校验和有效的冻结字符串，
  用于专门触发填充 / 版本 / 长度检查，而非用自身编码反证正确性。
"""

import pytest

from wallet_registry import Network, parse_address
from wallet_registry.bech32 import BECH32_CONST, BECH32M_CONST, bech32_decode

ETH = Network.ETHEREUM
BTC = Network.BITCOIN
SOL = Network.SOLANA


# ---------- EIP-55 ----------

# EIP-55 提案官方向量
EIP55_VALID = [
    "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed",
    "0xfB6916095ca1df60bB79Ce92cE3Ea74c37c5d359",
    "0xdbF03B407c01E7cD3CBea99509d93f8DDDC8C6FB",
    "0xD1220A0cf47c7B9Be7A2E6BA89F429762e7b9aDb",
]


@pytest.mark.parametrize("addr", EIP55_VALID)
def test_eip55_official_vectors(addr):
    assert parse_address(ETH, addr).canonical == addr


@pytest.mark.parametrize("addr", EIP55_VALID)
def test_eip55_case_aliases_same_key(addr):
    key = parse_address(ETH, addr).key
    assert parse_address(ETH, addr.lower()).key == key
    assert parse_address(ETH, "0x" + addr[2:].upper()).key == key
    assert parse_address(ETH, addr.lower()).canonical == addr


# 每个官方向量翻转最后一个十六进制字母的大小写 -> 校验和必错
EIP55_BAD_CHECKSUM = [
    "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAeD",
    "0xfB6916095ca1df60bB79Ce92cE3Ea74c37c5d359".replace("d359", "D359"),
    "0xdbF03B407c01E7cD3CBea99509d93f8DDDC8C6Fb",
    "0xD1220A0cf47c7B9Be7A2E6BA89F429762e7b9aDb".replace("9aDb", "9adB"),
]


@pytest.mark.parametrize("addr", EIP55_BAD_CHECKSUM)
def test_eip55_bad_checksum_rejected(addr):
    with pytest.raises(ValueError):
        parse_address(ETH, addr)


@pytest.mark.parametrize("addr", [
    "0X5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed",   # 大写 0X 前缀
    "5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed",     # 缺少 0x
    "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAe",    # 39 位
    "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAedd",  # 41 位
    "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAeg",   # 非十六进制字符
    "0x",                                            # 空主体
    "",
])
def test_evm_malformed_rejected(addr):
    with pytest.raises(ValueError):
        parse_address(ETH, addr)


# ---------- Bitcoin 传统地址 ----------

def test_p2pkh_genesis_vector():
    # 比特币创世地址，载荷为 Bitcoin Wiki 公开记录
    p = parse_address(BTC, "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")
    assert p.canonical == "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
    assert p.key.endswith(bytes.fromhex("62e907b15cbf27d5425399ebf6f0fb50ebb88f18"))


def test_p2sh_vector():
    # 公开文档中广泛引用的 P2SH 示例地址
    p = parse_address(BTC, "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy")
    assert p.canonical == "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy"
    assert p.key.endswith(bytes.fromhex("b472a266d0bd89c13706a4132ccfb16f7c3b9fcb"))


@pytest.mark.parametrize("addr", [
    "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNb",   # 篡改末位 -> 校验和错
    "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLz",   # 篡改末位
    "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfN",    # 截断
    "0A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",   # 非法 Base58 字符 0
])
def test_legacy_bad_checksum_rejected(addr):
    with pytest.raises(ValueError):
        parse_address(BTC, addr)


# ---------- Bitcoin 见证地址（BIP173 / BIP350）----------

def test_segwit_v0_p2wpkh_vector():
    # BIP173 主网示例，程序为 BIP173 公开记录
    p = parse_address(BTC, "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4")
    assert p.canonical == "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"
    assert p.key.endswith(bytes.fromhex("751e76e8199196d454941c45d1b3a323f1433bd6"))


def test_segwit_uppercase_alias():
    # BIP173 同一地址的全大写形式
    lower = parse_address(BTC, "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4")
    upper = parse_address(BTC, "BC1QW508D6QEJXTDG4Y5R3ZARVARY0C5XW7KV8F3T4")
    assert upper.key == lower.key
    assert upper.canonical == lower.canonical


def test_segwit_v16_vector():
    # BIP350 有效向量：v16，程序 0x751e
    p = parse_address(BTC, "BC1SW50QGDZ25J")
    assert p.canonical == "bc1sw50qgdz25j"
    assert p.key.endswith(b"\x75\x1e")


def test_segwit_v1_taproot_vector():
    # BIP86 测试向量地址：v1，32 字节程序
    p = parse_address(BTC, "bc1p5cyxnuxmeuwuvkwfem96lqzszd02n6xdcjrs20cac6yqjjwudpxqkedrcr")
    assert p.canonical == "bc1p5cyxnuxmeuwuvkwfem96lqzszd02n6xdcjrs20cac6yqjjwudpxqkedrcr"


SEGWIT_INVALID = [
    "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kg3g4ty",   # BIP173：校验和错误
    "BC1QW508D6QEJXTDG4Y5R3ZARVARY0C5XW7KV8F3T5",   # 篡改末位
    "tc1qw508d6qejxtdg4y5r3zarvary0c5xw7kg3g4ty",   # BIP173：hrp 非 bc
    "bc1Qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4",   # 混合大小写
    "bc1gmk9yu",                                     # BIP173：空数据段
    "bc1zw508d6qejxtdg4y5r3zarvaryvg6kdaj",          # BIP350：v2 误用 Bech32
    "bc1zw508d6qejxtdg4y5r3zarvaryvqyzf3du",         # BIP350：非法
    "bc13w508d6qejxtdg4y5r3zarvary0c5xw7kxflzvg",    # 未来见证版本 v17（校验和有效）
    "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kqq7e2cw9",  # v0 程序 21 字节（校验和有效）
    "bc1p4gajeh9s",                                  # v1 程序 1 字节（校验和有效）
    "bc1pqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqepcyyg",  # v1 程序 41 字节
    "bc1pzg6pa7r25f",                                # 尾部非零填充（校验和有效）
    "bc1" + "q" * 100,                               # 总长超过 90
]


@pytest.mark.parametrize("addr", SEGWIT_INVALID)
def test_segwit_invalid_rejected(addr):
    with pytest.raises(ValueError):
        parse_address(BTC, addr)


def test_bech32m_vectors():
    # BIP350 通用 bech32m 有效向量
    for addr in ["A1LQFN3A", "a1lqfn3a",
                 "an83characterlonghumanreadablepartthatcontainsthetheexcludedcharactersbioandnumber11sg7hg6",
                 "abcdef1l7aum6echk45nj3s0wdvt2fg8x9yrzpqzd3ryx",
                 "11llllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllllludsr8",
                 "split1checkupstagehandshakeupstreamerranterredcaperredlc445v",
                 "?1v759aa"]:
        _, _, spec = bech32_decode(addr)
        assert spec == BECH32M_CONST


def test_bech32_vectors():
    # BIP173 通用 bech32 有效向量
    for addr in ["A12UEL5L", "a12uel5l",
                 "11qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqc8247j",
                 "split1checkupstagehandshakeupstreamerranterredcaperred2y9e3w",
                 "?1ezyfcl"]:
        _, _, spec = bech32_decode(addr)
        assert spec == BECH32_CONST


def test_bech32_invalid_vectors():
    # BIP173 通用无效向量
    for addr in [" 1nwldj5", "\x7f1axkwrx", "\x801eym55h",
                 "an84characterslonghumanreadablepartthatcontainsthetheexcludedcharactersbioandnumber11d6pts4",
                 "pzry9x0s0muk", "1pzry9x0s0muk", "x1b4n0q5v", "li1dgmt3",
                 "de1lg7wt\xff", "A1G7SGD8", "10a06t8", "1qzzfhee"]:
        with pytest.raises(ValueError):
            bech32_decode(addr)


# ---------- Solana ----------

def test_solana_all_zeros_leading():
    # 32 个前导零字节（系统程序地址）：前导零必须计入长度
    p = parse_address(SOL, "11111111111111111111111111111111")
    assert p.canonical == "11111111111111111111111111111111"
    assert p.key.endswith(b"\x00" * 32)


def test_solana_token_program():
    # SPL Token 程序地址（公开）
    p = parse_address(SOL, "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
    assert p.canonical == "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"


@pytest.mark.parametrize("addr", [
    "1111111111111111111111111111111",     # 31 字节
    "111111111111111111111111111111111",   # 33 字节
    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5D",   # 截断
    "0okenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",  # 非法字符 0
    "OokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",  # 非法字符 O
    "",
])
def test_solana_invalid_rejected(addr):
    with pytest.raises(ValueError):
        parse_address(SOL, addr)
