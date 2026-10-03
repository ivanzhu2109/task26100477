"""登记行为测试：别名合并、跨链隔离、原子性、持久化与性能。"""

import os
import tempfile
import time
import unittest

from walletlib import (
    BITCOIN,
    ETHEREUM,
    POLYGON,
    SOLANA,
    BatchTooLargeError,
    InvalidAddressError,
    WalletRegistry,
)
from walletlib.base58 import b58encode

ETH_ADDR = "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed"
# 同一 hash160 (751e76e8199196d454941c45d1b3a323f1433bd6) 的三种比特币形态
BTC_P2PKH = "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"
BTC_P2SH = "3CNHUhP3uyB9EUtRLsmvFUmvGdjGdkTxJw"
BTC_P2WPKH = "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"
SOL_ADDR = "4uQeVj5tqViQh7yWWGStvkEG1Zmhx6uasJtWCJziofM"


class RegistryTestCase(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        os.unlink(self.db_path)
        self.reg = WalletRegistry(self.db_path)

    def tearDown(self):
        self.reg.close()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)


class TestMerging(RegistryTestCase):
    def test_case_aliases_same_wallet(self):
        lower = ETH_ADDR.lower()
        upper = "0x" + ETH_ADDR[2:].upper()
        ids = self.reg.register_batch([(ETHEREUM, lower)])
        self.assertEqual(self.reg.query(ETHEREUM, ETH_ADDR), ids[0])
        self.assertEqual(self.reg.query(ETHEREUM, upper), ids[0])
        # 三种写法同批登记只产生一个钱包
        ids = self.reg.register_batch(
            [(ETHEREUM, lower), (ETHEREUM, ETH_ADDR), (ETHEREUM, upper)])
        self.assertEqual(len(set(ids)), 1)
        self.assertEqual(self.reg.count(), 1)

    def test_bech32_case_alias_same_wallet(self):
        ids = self.reg.register_batch([(BITCOIN, BTC_P2WPKH.upper())])
        self.assertEqual(self.reg.query(BITCOIN, BTC_P2WPKH), ids[0])
        self.assertEqual(self.reg.count(), 1)

    def test_cross_chain_same_text_distinct(self):
        eth_id, poly_id = self.reg.register_batch(
            [(ETHEREUM, ETH_ADDR), (POLYGON, ETH_ADDR)])
        self.assertNotEqual(eth_id, poly_id)
        self.assertEqual(self.reg.count(), 2)

    def test_bitcoin_address_types_distinct(self):
        # 相同载荷的 P2PKH / P2SH / P2WPKH 不能合并
        ids = self.reg.register_batch(
            [(BITCOIN, BTC_P2PKH), (BITCOIN, BTC_P2SH), (BITCOIN, BTC_P2WPKH)])
        self.assertEqual(len(set(ids)), 3)
        self.assertEqual(self.reg.count(), 3)

    def test_solana_case_not_merged(self):
        other = SOL_ADDR[:-1] + ("m" if SOL_ADDR[-1] == "M" else "M")
        ids = self.reg.register_batch([(SOLANA, SOL_ADDR), (SOLANA, other)])
        self.assertEqual(len(set(ids)), 2)

    def test_persistence_across_reopen(self):
        ids = self.reg.register_batch([
            (ETHEREUM, ETH_ADDR.lower()),
            (BITCOIN, BTC_P2PKH),
            (BITCOIN, BTC_P2WPKH.upper()),
            (SOLANA, SOL_ADDR),
        ])
        self.reg.close()
        self.reg = WalletRegistry(self.db_path)
        self.assertEqual(self.reg.query(ETHEREUM, ETH_ADDR), ids[0])
        self.assertEqual(self.reg.query(BITCOIN, BTC_P2PKH), ids[1])
        self.assertEqual(self.reg.query(BITCOIN, BTC_P2WPKH.lower()), ids[2])
        self.assertEqual(self.reg.query(SOLANA, SOL_ADDR), ids[3])
        self.assertEqual(self.reg.count(), 4)
        # 重新登记同一批，标识不变、数量不变
        again = self.reg.register_batch([
            (ETHEREUM, ETH_ADDR),
            (BITCOIN, BTC_P2PKH),
            (BITCOIN, BTC_P2WPKH),
            (SOLANA, SOL_ADDR),
        ])
        self.assertEqual(again, ids)
        self.assertEqual(self.reg.count(), 4)


class TestBatchSemantics(RegistryTestCase):
    def _mixed_batch(self, n, start=0):
        """构造 n 条四网络混合、互不相同的合法批次。"""
        entries = []
        for i in range(n):
            k = start + i
            kind = k % 4
            if kind == 0:
                entries.append((ETHEREUM, "0x%040x" % (k + 1)))
            elif kind == 1:
                entries.append((POLYGON, "0x%040x" % (k + 2)))
            elif kind == 2:
                entries.append((SOLANA, b58encode((k + 3).to_bytes(32, "big"))))
            else:
                entries.append(self._btc(k))
        return entries

    @staticmethod
    def _btc(k):
        # 用不同的合法 P2WPKH：程序为 20 字节，由 k 派生，bech32 编码
        from walletlib.bech32 import _hrp_expand, _polymod, CHARSET, BECH32_CONST
        program = k.to_bytes(20, "big")
        acc, bits, data = 0, 0, [0]
        for byte in program:
            acc = (acc << 8) | byte
            bits += 8
            while bits >= 5:
                bits -= 5
                data.append((acc >> bits) & 31)
        if bits:
            data.append((acc << (5 - bits)) & 31)
        polymod = _polymod(_hrp_expand("bc") + data + [0] * 6) ^ BECH32_CONST
        data += [(polymod >> 5 * (5 - i)) & 31 for i in range(6)]
        return BITCOIN, "bc1" + "".join(CHARSET[d] for d in data)

    def test_batch_too_large(self):
        with self.assertRaises(BatchTooLargeError):
            self.reg.register_batch([(ETHEREUM, ETH_ADDR)] * 501)

    def test_atomic_rollback_then_fix_then_resubmit(self):
        # 500 条混合批次，最后一条无效 -> 数量不变
        batch = self._mixed_batch(499)
        batch.append((ETHEREUM, "0xZZZ"))
        with self.assertRaises(InvalidAddressError):
            self.reg.register_batch(batch)
        self.assertEqual(self.reg.count(), 0)
        # 修正最后一条后提交
        batch[-1] = (SOLANA, SOL_ADDR)
        ids = self.reg.register_batch(batch)
        unique = len({(n, self.reg.query(n, a)) for n, a in batch})
        self.assertEqual(self.reg.count(), unique)
        self.assertEqual(len(ids), 500)
        # 重复提交同一批次：结果与数量均不变
        again = self.reg.register_batch(batch)
        self.assertEqual(again, ids)
        self.assertEqual(self.reg.count(), unique)

    def test_duplicates_within_batch(self):
        batch = [(ETHEREUM, ETH_ADDR.lower()), (ETHEREUM, ETH_ADDR),
                 (ETHEREUM, "0x" + ETH_ADDR[2:].upper()), (SOLANA, SOL_ADDR)]
        ids = self.reg.register_batch(batch)
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(ids[1], ids[2])
        self.assertNotEqual(ids[0], ids[3])
        self.assertEqual(self.reg.count(), 2)


class TestPerformance(RegistryTestCase):
    def test_500_mixed_batch_with_100k_registered(self):
        # 预登记 10 万个 Solana 钱包（无 keccak 开销，聚焦登记路径）
        counter = 0
        for _ in range(200):
            batch = []
            for _ in range(500):
                counter += 1
                batch.append((SOLANA, b58encode(counter.to_bytes(32, "big"))))
            self.reg.register_batch(batch)
        self.assertEqual(self.reg.count(), 100_000)
        # 500 条混合网络批次计时
        mixed = []
        for i in range(500):
            kind = i % 4
            if kind == 0:
                mixed.append((ETHEREUM, "0x%040x" % (10_000_000 + i)))
            elif kind == 1:
                mixed.append((POLYGON, "0x%040x" % (20_000_000 + i)))
            elif kind == 2:
                mixed.append((BITCOIN, TestBatchSemantics._btc(500_000 + i)[1]))
            else:
                mixed.append((SOLANA, b58encode((100_000_000 + i).to_bytes(32, "big"))))
        start = time.perf_counter()
        ids = self.reg.register_batch(mixed)
        elapsed = time.perf_counter() - start
        self.assertEqual(len(ids), 500)
        self.assertEqual(self.reg.count(), 100_500)
        self.assertLess(elapsed, 2.0, f"500 条混合批次耗时 {elapsed:.2f}s")


if __name__ == "__main__":
    unittest.main()
