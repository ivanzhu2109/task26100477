"""Bech32 / Bech32m 解码（BIP173 / BIP350），仅实现解码与校验。"""

BECH32_CONST: int = 1
BECH32M_CONST: int = 0x2BC830A3

_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
_INDEX = {ch: i for i, ch in enumerate(_CHARSET)}


def _polymod(values: list[int]) -> int:
    generators = (0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3)
    chk = 1
    for value in values:
        top = chk >> 25
        chk = ((chk & 0x1FFFFFF) << 5) ^ value
        for i in range(5):
            if (top >> i) & 1:
                chk ^= generators[i]
    return chk


def _hrp_expand(hrp: str) -> list[int]:
    return [ord(c) >> 5 for c in hrp] + [0] + [ord(c) & 31 for c in hrp]


def bech32_decode(text: str) -> tuple[str, list[int], int]:
    """解码 bech32/bech32m 字符串。

    返回 (hrp, data5, spec_const)，spec_const 为 BECH32_CONST 或
    BECH32M_CONST。任何格式或校验和错误抛 ValueError。
    """
    if not text or len(text) > 90:
        raise ValueError("Bech32 长度非法")
    if text.lower() != text and text.upper() != text:
        raise ValueError("Bech32 禁止混合大小写")
    text = text.lower()
    if any(ord(c) < 33 or ord(c) > 126 for c in text):
        raise ValueError("Bech32 含非法字符")
    pos = text.rfind("1")
    if pos < 1 or pos + 7 > len(text):
        raise ValueError("Bech32 分隔符位置非法")
    hrp = text[:pos]
    data = []
    for ch in text[pos + 1:]:
        digit = _INDEX.get(ch)
        if digit is None:
            raise ValueError(f"非法 Bech32 字符: {ch!r}")
        data.append(digit)
    check = _polymod(_hrp_expand(hrp) + data)
    if check == BECH32_CONST:
        spec = BECH32_CONST
    elif check == BECH32M_CONST:
        spec = BECH32M_CONST
    else:
        raise ValueError("Bech32 校验和错误")
    return hrp, data[:-6], spec


def convertbits(data: list[int], frombits: int, tobits: int, pad: bool) -> list[int]:
    """通用位组转换。pad=False 时尾部非零填充或超过 4 位填充抛 ValueError。"""
    acc = 0
    bits = 0
    result = []
    maxv = (1 << tobits) - 1
    max_acc = (1 << (frombits + tobits - 1)) - 1
    for value in data:
        if value < 0 or value >> frombits:
            raise ValueError("位组数值越界")
        acc = ((acc << frombits) | value) & max_acc
        bits += frombits
        while bits >= tobits:
            bits -= tobits
            result.append((acc >> bits) & maxv)
    if pad:
        if bits:
            result.append((acc << (tobits - bits)) & maxv)
    elif bits >= frombits or ((acc << (tobits - bits)) & maxv):
        raise ValueError("尾部填充非法")
    return result
