"""BIP173 Bech32 与 BIP350 Bech32m 解码。"""

CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
_INDEX = {ch: i for i, ch in enumerate(CHARSET)}

BECH32_CONST = 1
BECH32M_CONST = 0x2BC830A3


def _hrp_expand(hrp: str) -> list[int]:
    return [ord(c) >> 5 for c in hrp] + [0] + [ord(c) & 31 for c in hrp]


def _polymod(values: list[int]) -> int:
    generators = (0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3)
    chk = 1
    for v in values:
        top = chk >> 25
        chk = ((chk & 0x1FFFFFF) << 5) ^ v
        for i in range(5):
            if (top >> i) & 1:
                chk ^= generators[i]
    return chk


def _verify_checksum(hrp: str, data: list[int]) -> int:
    """返回校验常数（bech32 或 bech32m），失败抛 ValueError。"""
    check = _polymod(_hrp_expand(hrp) + data)
    if check == BECH32_CONST:
        return BECH32_CONST
    if check == BECH32M_CONST:
        return BECH32M_CONST
    raise ValueError("校验和错误")


def _convertbits_5to8(data: list[int]) -> bytes:
    """5 位组还原为字节；尾部只允许 0..4 位零填充，否则抛 ValueError。"""
    acc = 0
    bits = 0
    out = bytearray()
    for value in data:
        acc = (acc << 5) | value
        bits += 5
        while bits >= 8:
            bits -= 8
            out.append((acc >> bits) & 0xFF)
    if bits > 4:
        raise ValueError("尾部填充超过 4 位")
    if (acc & ((1 << bits) - 1)) != 0:
        raise ValueError("尾部填充非零")
    return bytes(out)


def decode_segwit(text: str) -> tuple[int, bytes]:
    """校验并解码隔离见证地址，返回 (见证版本, 程序字节)。

    规则：hrp 为 "bc"，总长 <= 90，禁止混合大小写；
    v0 使用 bech32 且程序为 20 或 32 字节；
    v1..v16 使用 bech32m 且程序为 2..40 字节；
    5 位组还原 8 位时尾部只允许 0..4 位零填充。
    任何不合法抛出 ValueError。
    """
    if not text:
        raise ValueError("空地址")
    if text.lower() != text and text.upper() != text:
        raise ValueError("禁止混合大小写")
    lowered = text.lower()
    if len(lowered) > 90:
        raise ValueError("地址超过 90 字符")
    if any(ord(c) < 33 or ord(c) > 126 for c in lowered):
        raise ValueError("含非法字符")
    pos = lowered.rfind("1")
    if pos < 1 or pos + 7 > len(lowered):
        raise ValueError("分隔符位置非法")
    hrp = lowered[:pos]
    if hrp != "bc":
        raise ValueError("前缀必须为 bc")
    data = []
    for ch in lowered[pos + 1:]:
        digit = _INDEX.get(ch)
        if digit is None:
            raise ValueError(f"非法 bech32 字符: {ch!r}")
        data.append(digit)
    const = _verify_checksum(hrp, data)
    payload5 = data[:-6]
    if not payload5:
        raise ValueError("缺少见证版本")
    version = payload5[0]
    if version > 16:
        raise ValueError("见证版本超过 16")
    program = _convertbits_5to8(payload5[1:])
    if version == 0:
        if const != BECH32_CONST:
            raise ValueError("v0 必须使用 bech32")
        if len(program) not in (20, 32):
            raise ValueError("v0 程序必须为 20 或 32 字节")
    else:
        if const != BECH32M_CONST:
            raise ValueError("v1..v16 必须使用 bech32m")
        if not (2 <= len(program) <= 40):
            raise ValueError("v1..v16 程序必须为 2..40 字节")
    return version, program
