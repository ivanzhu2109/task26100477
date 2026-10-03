"""Base58 与 Base58Check 编解码（比特币 / Solana）。"""

import hashlib

ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_INDEX = {ch: i for i, ch in enumerate(ALPHABET)}


def b58decode(text: str) -> bytes:
    """解码 Base58 文本；非法字符抛出 ValueError。前导零计入长度。"""
    if not text:
        raise ValueError("空 Base58 文本")
    value = 0
    for ch in text:
        digit = _INDEX.get(ch)
        if digit is None:
            raise ValueError(f"非法 Base58 字符: {ch!r}")
        value = value * 58 + digit
    body = value.to_bytes((value.bit_length() + 7) // 8, "big") if value else b""
    leading_zeros = len(text) - len(text.lstrip("1"))
    return b"\x00" * leading_zeros + body


def b58encode(data: bytes) -> str:
    """编码为 Base58 文本。"""
    value = int.from_bytes(data, "big")
    chars = []
    while value:
        value, rem = divmod(value, 58)
        chars.append(ALPHABET[rem])
    leading_zeros = len(data) - len(data.lstrip(b"\x00"))
    return "1" * leading_zeros + "".join(reversed(chars))


def b58check_decode(text: str) -> tuple[int, bytes]:
    """Base58Check 解码，返回 (版本字节, 载荷)。校验失败抛 ValueError。"""
    raw = b58decode(text)
    if len(raw) < 5:
        raise ValueError("Base58Check 数据过短")
    body, checksum = raw[:-4], raw[-4:]
    digest = hashlib.sha256(hashlib.sha256(body).digest()).digest()
    if checksum != digest[:4]:
        raise ValueError("Base58Check 校验和错误")
    return body[0], body[1:]
