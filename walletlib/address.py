"""各网络地址解析与规范化。"""

from dataclasses import dataclass

from .base58 import b58decode, b58check_decode
from .bech32 import decode_segwit
from .errors import InvalidAddressError, UnsupportedNetworkError
from .keccak import keccak256

ETHEREUM = "ethereum"
POLYGON = "polygon"
BITCOIN = "bitcoin"
SOLANA = "solana"

SUPPORTED_NETWORKS = (ETHEREUM, POLYGON, BITCOIN, SOLANA)

_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")


@dataclass(frozen=True)
class ParsedAddress:
    """解析结果：所属网络与规范地址文本。"""

    network: str
    canonical: str


def _eip55_checksum(body_lower: str) -> str:
    """对全小写十六进制主体计算 EIP-55 校验和形式。"""
    digest = keccak256(body_lower.encode("ascii")).hex()
    out = []
    for ch, h in zip(body_lower, digest):
        if ch in "abcdef" and int(h, 16) >= 8:
            out.append(ch.upper())
        else:
            out.append(ch)
    return "".join(out)


def _parse_evm(network: str, text: str) -> ParsedAddress:
    if not text.startswith("0x"):
        raise InvalidAddressError("缺少小写 0x 前缀")
    body = text[2:]
    if len(body) != 40:
        raise InvalidAddressError("主体必须为 40 位十六进制")
    if any(ch not in _HEX_DIGITS for ch in body):
        raise InvalidAddressError("主体含非十六进制字符")
    if body.islower() or body.isupper():
        canonical = _eip55_checksum(body.lower())
    else:
        canonical = _eip55_checksum(body.lower())
        if body != canonical:
            raise InvalidAddressError("混合大小写不满足 EIP-55 校验和")
    return ParsedAddress(network, "0x" + canonical)


def _parse_bitcoin(text: str) -> ParsedAddress:
    # 隔离见证地址（bech32/bech32m，前缀 bc1）
    if text.lower().startswith("bc1"):
        try:
            decode_segwit(text)
        except ValueError as exc:
            raise InvalidAddressError(str(exc)) from exc
        return ParsedAddress(BITCOIN, text.lower())
    # 传统 Base58Check 地址
    try:
        version, payload = b58check_decode(text)
    except ValueError as exc:
        raise InvalidAddressError(str(exc)) from exc
    if version not in (0, 5):
        raise InvalidAddressError("版本字节必须为 0(P2PKH) 或 5(P2SH)")
    if len(payload) != 20:
        raise InvalidAddressError("载荷必须为 20 字节")
    return ParsedAddress(BITCOIN, text)


def _parse_solana(text: str) -> ParsedAddress:
    try:
        raw = b58decode(text)
    except ValueError as exc:
        raise InvalidAddressError(str(exc)) from exc
    if len(raw) != 32:
        raise InvalidAddressError("解码结果必须为 32 字节")
    return ParsedAddress(SOLANA, text)


def parse_address(network: str, text: str) -> ParsedAddress:
    """解析单条地址，返回规范形式；无效时抛 InvalidAddressError。"""
    if network not in SUPPORTED_NETWORKS:
        raise UnsupportedNetworkError(f"不支持的网络: {network!r}")
    if not isinstance(text, str) or not text:
        raise InvalidAddressError("地址不能为空")
    if network in (ETHEREUM, POLYGON):
        return _parse_evm(network, text)
    if network == BITCOIN:
        return _parse_bitcoin(text)
    return _parse_solana(text)
