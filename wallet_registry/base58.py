"""Base58 与 Base58Check 编解码（Bitcoin / Solana）。"""

import hashlib

_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_INDEX = {ch: i for i, ch in enumerate(_ALPHABET)}


def b58decode(text: str) -> bytes:
    """解码 Base58 字符串，保留前导零字节。非法字符抛 ValueError。"""
    if not text:
        raise ValueError("空的 Base58 串")
    value = 0
    for ch in text:
        digit = _INDEX.get(ch)
        if digit is None:
            raise ValueError(f"非法 Base58 字符: {ch!r}")
        value = value * 58 + digit
    # 前导 '1' 对应前导零字节
    leading_zeros = len(text) - len(text.lstrip("1"))
    body = value.to_bytes((value.bit_length() + 7) // 8, "big") if value else b""
    return b"\x00" * leading_zeros + body


def b58check_decode(text: str) -> tuple[int, bytes]:
    """解码 Base58Check，返回 (版本字节, 载荷)。校验失败抛 ValueError。"""
    raw = b58decode(text)
    if len(raw) < 5:
        raise ValueError("Base58Check 数据过短")
    body, checksum = raw[:-4], raw[-4:]
    expect = hashlib.sha256(hashlib.sha256(body).digest()).digest()[:4]
    if checksum != expect:
        raise ValueError("Base58Check 校验和错误")
    return body[0], body[1:]
