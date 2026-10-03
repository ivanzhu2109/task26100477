"""各网络地址解析：返回规范地址与所属网络。"""

import enum
import re
from dataclasses import dataclass

from .base58 import b58check_decode, b58decode
from .bech32 import BECH32_CONST, BECH32M_CONST, bech32_decode, convertbits
from .keccak import keccak256


class Network(enum.Enum):
    ETHEREUM = "ethereum"
    POLYGON = "polygon"
    BITCOIN = "bitcoin"
    SOLANA = "solana"


@dataclass(frozen=True)
class ParsedAddress:
    network: Network
    canonical: str  # 规范地址文本
    key: bytes      # 用于去重的规范化键（含网络与地址种类）


_HEX40 = re.compile(r"[0-9a-fA-F]{40}")


def _eip55(hex_body_lower: str) -> str:
    """对小写 hex 主体计算 EIP-55 校验和形式。"""
    digest = keccak256(hex_body_lower.encode("ascii")).hex()
    out = []
    for ch, h in zip(hex_body_lower, digest):
        out.append(ch.upper() if ch in "abcdef" and int(h, 16) >= 8 else ch)
    return "0x" + "".join(out)


def _parse_evm(network: Network, address: str) -> ParsedAddress:
    if not address.startswith("0x"):
        raise ValueError("EVM 地址必须以小写 0x 开头")
    body = address[2:]
    if not _HEX40.fullmatch(body):
        raise ValueError("EVM 地址主体必须为 40 位十六进制")
    if body != body.lower() and body != body.upper():
        # 混合大小写必须满足 EIP-55
        if _eip55(body.lower()) != "0x" + body:
            raise ValueError("EIP-55 校验和错误")
    canonical = _eip55(body.lower())
    key = network.value.encode() + b"\x00" + bytes.fromhex(body.lower())
    return ParsedAddress(network, canonical, key)


def _parse_bitcoin(address: str) -> ParsedAddress:
    prefix = b"bitcoin\x00"
    # 传统地址：Base58Check，版本 0 (P2PKH) 或 5 (P2SH)，载荷 20 字节
    if address[:1] in ("1", "3"):
        version, payload = b58check_decode(address)
        if version not in (0, 5):
            raise ValueError(f"不支持的版本字节: {version}")
        if len(payload) != 20:
            raise ValueError("传统地址载荷必须为 20 字节")
        key = prefix + b"L" + bytes([version]) + payload
        return ParsedAddress(Network.BITCOIN, address, key)
    # 见证地址：Bech32/Bech32m，前缀 bc
    hrp, data5, spec = bech32_decode(address)
    if hrp != "bc":
        raise ValueError("见证地址前缀必须为 bc")
    if not data5:
        raise ValueError("缺少见证版本")
    version = data5[0]
    if version > 16:
        raise ValueError("见证版本必须在 0..16")
    program = bytes(convertbits(data5[1:], 5, 8, pad=False))
    if version == 0:
        if spec != BECH32_CONST:
            raise ValueError("v0 见证地址必须使用 Bech32")
        if len(program) not in (20, 32):
            raise ValueError("v0 程序只允许 20 或 32 字节")
    else:
        if spec != BECH32M_CONST:
            raise ValueError("v1..v16 见证地址必须使用 Bech32m")
        if not 2 <= len(program) <= 40:
            raise ValueError("v1..v16 程序必须为 2..40 字节")
    key = prefix + b"W" + bytes([version]) + program
    return ParsedAddress(Network.BITCOIN, address.lower(), key)


def _parse_solana(address: str) -> ParsedAddress:
    raw = b58decode(address)
    if len(raw) != 32:
        raise ValueError("Solana 地址解码后必须为 32 字节")
    key = b"solana\x00" + raw
    return ParsedAddress(Network.SOLANA, address, key)


def parse_address(network: Network, address: str) -> ParsedAddress:
    """解析单条地址。无效地址抛 ValueError。"""
    if not isinstance(address, str) or not address:
        raise ValueError("地址必须为非空字符串")
    if network in (Network.ETHEREUM, Network.POLYGON):
        return _parse_evm(network, address)
    if network is Network.BITCOIN:
        return _parse_bitcoin(address)
    if network is Network.SOLANA:
        return _parse_solana(address)
    raise ValueError(f"不支持的网络: {network!r}")
