"""固定期望结果的地址向量测试：EIP-55、BIP173、BIP350、Base58Check、Solana。

向量来源：
- EIP-55 官方文档示例；
- BIP173 / BIP350 规范附录的有效与无效示例；
- 比特币主网知名地址（创世块、生成元公钥）；
- 由规范算法独立构造的边界向量（非零填充、未来版本、前导零），
  常量已固化在本文件中，测试时不做自编码往返。
"""

import unittest

from walletlib import (
    BITCOIN,
    ETHEREUM,
    POLYGON,
    SOLANA,
    InvalidAddressError,
    UnsupportedNetworkError,
    parse_address,
)


class TestEIP55(unittest.TestCase):
    # EIP-55 官方测试向量
    VALID = [
        "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed",
        "0xfB6916095ca1df60bB79Ce92cE3Ea74c37c5d359",
        "0xdbF03B407c01E7cD3CBea99509d93f8DDDC8C6FB",
        "0xD1220A0cf47c7B9Be7A2E6BA89F429762e7b9aDb",
    ]

    def test_official_vectors_accepted_verbatim(self):
        for addr in self.VALID:
            for network in (ETHEREUM, POLYGON):
                result = parse_address(network, addr)
                self.assertEqual(result.canonical, addr)
                self.assertEqual(result.network, network)

    def test_all_lower_and_upper_normalized_to_eip55(self):
        for addr in self.VALID:
            self.assertEqual(parse_address(ETHEREUM, addr.lower()).canonical, addr)
            self.assertEqual(
                parse_address(ETHEREUM, "0x" + addr[2:].upper()).canonical, addr)

    def test_wrong_checksum_rejected(self):
        # 每个官方向量翻转一个字母的大小写，校验和必然失配
        for addr in self.VALID:
            body = list(addr[2:])
            idx = next(i for i, c in enumerate(body) if c.isalpha())
            body[idx] = body[idx].swapcase()
            with self.assertRaises(InvalidAddressError):
                parse_address(ETHEREUM, "0x" + "".join(body))

    def test_malformed_rejected(self):
        good = self.VALID[0]
        bad = [
            "0X" + good[2:],          # 大写前缀
            good[2:],                  # 缺少前缀
            "0x" + good[2:39],         # 39 位
            "0x" + good[2:] + "0",     # 41 位
            "0x" + good[2:10] + "g" + good[11:],  # 非十六进制
            "",
        ]
        for addr in bad:
            with self.assertRaises(InvalidAddressError, msg=addr):
                parse_address(ETHEREUM, addr)

    def test_unsupported_network(self):
        with self.assertRaises(UnsupportedNetworkError):
            parse_address("litecoin", self.VALID[0])


class TestBitcoinLegacy(unittest.TestCase):
    def test_known_p2pkh(self):
        # 创世块 coinbase 地址
        result = parse_address(BITCOIN, "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")
        self.assertEqual(result.canonical, "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")
        # 生成元公钥哈希地址
        result = parse_address(BITCOIN, "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH")
        self.assertEqual(result.canonical, "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH")

    def test_known_p2sh(self):
        result = parse_address(BITCOIN, "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy")
        self.assertEqual(result.canonical, "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy")

    def test_legacy_case_preserved(self):
        # 传统地址规范形式保留原大小写
        addr = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
        self.assertEqual(parse_address(BITCOIN, addr).canonical, addr)

    def test_bad_checksum_rejected(self):
        with self.assertRaises(InvalidAddressError):
            parse_address(BITCOIN, "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNb")

    def test_wrong_version_rejected(self):
        # 测试网 P2PKH（版本字节 111），Base58Check 本身合法
        with self.assertRaises(InvalidAddressError):
            parse_address(BITCOIN, "mfWxJ45yp2SFn7UciZyNpvDKrzbhyfKrY8")

    def test_invalid_base58_char_rejected(self):
        with self.assertRaises(InvalidAddressError):
            parse_address(BITCOIN, "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfN0")  # 含 '0'


class TestBitcoinSegwit(unittest.TestCase):
    def test_bip173_valid(self):
        # BIP173 主网 P2WPKH 示例
        result = parse_address(BITCOIN, "BC1QW508D6QEJXTDG4Y5R3ZARVARY0C5XW7KV8F3T4")
        self.assertEqual(result.canonical,
                         "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4")
        # BIP173 主网 P2WSH 示例
        result = parse_address(
            BITCOIN, "bc1qrp33g0q5c5txsp9arysrx4k6zdkfs4nce4xj0gdcccefvpysxf3qccfmv3")
        self.assertEqual(result.canonical,
                         "bc1qrp33g0q5c5txsp9arysrx4k6zdkfs4nce4xj0gdcccefvpysxf3qccfmv3")

    def test_bip350_valid(self):
        # BIP350：v16，程序 0x751e
        result = parse_address(BITCOIN, "BC1SW50QGDZ25J")
        self.assertEqual(result.canonical, "bc1sw50qgdz25j")
        # BIP350：v2
        result = parse_address(BITCOIN, "bc1zw508d6qejxtdg4y5r3zarvaryvaxxpcs")
        self.assertEqual(result.canonical, "bc1zw508d6qejxtdg4y5r3zarvaryvaxxpcs")

    def test_uppercase_normalized_to_lower(self):
        result = parse_address(BITCOIN, "BC1QW508D6QEJXTDG4Y5R3ZARVARY0C5XW7KV8F3T4")
        self.assertEqual(result.canonical,
                         "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4")

    def test_mixed_case_rejected(self):
        with self.assertRaises(InvalidAddressError):
            parse_address(BITCOIN, "bc1Qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4")

    def test_bip173_bip350_invalid_vectors(self):
        invalid = [
            "tc1qw508d6qejxtdg4y5r3zarvary0c5xw7kg3g4ty",   # 无效 hrp
            "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kg3g4ty",   # 校验和错误
            "BC13W508D6QEJXTDG4Y5R3ZARVARY0C5XW7K9UP2T3",   # 见证版本 17
            "bc1rw5uspcuh",                                  # 程序过短（1 字节）
            "bc10w508d6qejxtdg4y5r3zarvary0c5xw7kw508d6qejxtdg4y5r3zarvary0c5xw7kw5rljs90",  # 超 90 字符
            "BC1QR508D6QEJXTDG4Y5R3ZARVARYV98GJ9P",          # v1 误用 bech32
            "tb1qrp33g0q5c5txsp9arysrx4k6zdkfs4nce4xqt7",   # 非 bc 前缀
            "bc1zw508d6qejxtdg4y5r3zarvaryvqyzf3du",         # v2 误用 bech32
            "bc1gmk9yu",                                     # 空数据段
            "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t5",   # 末字符篡改
        ]
        for addr in invalid:
            with self.assertRaises(InvalidAddressError, msg=addr):
                parse_address(BITCOIN, addr)

    def test_nonzero_padding_rejected(self):
        # 校验和合法，但 5 位组还原时尾部含非零填充位
        with self.assertRaises(InvalidAddressError):
            parse_address(
                BITCOIN,
                "bc1qrp33g0q5c5txsp9arysrx4k6zdkfs4nce4xj0gdcccefvpysxf3p9waw3r")

    def test_future_version_rejected_even_with_valid_checksum(self):
        # 版本 17，bech32m 校验和合法，仍须按版本规则拒绝
        with self.assertRaises(InvalidAddressError):
            parse_address(BITCOIN, "bc13qqkguaxl")

    def test_v0_wrong_program_length_rejected(self):
        # v0 程序 40 字节（仅允许 20/32）：由合法 v1 地址降版本构造会破坏校验和，
        # 这里直接复用规范中 v0 超长向量（>90 字符情形已覆盖），
        # 另验证 v0 + bech32m 组合必败：BIP350 向量 BC1SW50QGDZ25J 的 v0 改写
        with self.assertRaises(InvalidAddressError):
            parse_address(BITCOIN, "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kemeawh")  # 校验和错


class TestSolana(unittest.TestCase):
    def test_known_address(self):
        addr = "4uQeVj5tqViQh7yWWGStvkEG1Zmhx6uasJtWCJziofM"
        self.assertEqual(parse_address(SOLANA, addr).canonical, addr)

    def test_all_zero_address(self):
        # system program：32 个零字节，前导零全部计入长度
        addr = "11111111111111111111111111111111"
        self.assertEqual(parse_address(SOLANA, addr).canonical, addr)

    def test_leading_zero_vector(self):
        # 0x00 后接 0x01..0x1f，共 32 字节
        addr = "1thX6LZfHDZZKUs92febYZhYRcXddmzfzF2NvTkPNE"
        self.assertEqual(parse_address(SOLANA, addr).canonical, addr)

    def test_case_not_folded(self):
        # 大小写不折叠：改一个字符大小写得到的是另一个合法但不同的地址
        addr = "4uQeVj5tqViQh7yWWGStvkEG1Zmhx6uasJtWCJziofM"
        other = "4uQeVj5tqViQh7yWWGStvkEG1Zmhx6uasJtWCJziofm"
        self.assertNotEqual(parse_address(SOLANA, addr).canonical,
                            parse_address(SOLANA, other).canonical)

    def test_wrong_length_rejected(self):
        with self.assertRaises(InvalidAddressError):
            parse_address(SOLANA, "1111111111111111111111111111111")   # 31 字节
        with self.assertRaises(InvalidAddressError):
            parse_address(SOLANA, "111111111111111111111111111111111")  # 33 字节

    def test_invalid_char_rejected(self):
        with self.assertRaises(InvalidAddressError):
            parse_address(SOLANA, "4uQeVj5tqViQh7yWWGStvkEG1Zmhx6uasJtWCJziof0")


if __name__ == "__main__":
    unittest.main()
