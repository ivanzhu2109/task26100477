"""纯 Python Keccak-256（以太坊使用的原始 Keccak，非 SHA3-256）。

与 SHA3-256 的区别仅在填充域分隔符：Keccak 用 0x01，SHA3 用 0x06。
"""

_MASK64 = (1 << 64) - 1

_ROT = (
    (0, 36, 3, 41, 18),
    (1, 44, 10, 45, 2),
    (62, 6, 43, 15, 61),
    (28, 55, 25, 21, 56),
    (27, 20, 39, 8, 14),
)

_RC = (
    0x0000000000000001, 0x0000000000008082, 0x800000000000808A,
    0x8000000080008000, 0x000000000000808B, 0x0000000080000001,
    0x8000000080008081, 0x8000000000008009, 0x000000000000008A,
    0x0000000000000088, 0x0000000080008009, 0x000000008000000A,
    0x000000008000808B, 0x800000000000008B, 0x8000000000008089,
    0x8000000000008003, 0x8000000000008002, 0x8000000000000080,
    0x000000000000800A, 0x800000008000000A, 0x8000000080008081,
    0x8000000000008080, 0x0000000080000001, 0x8000000080008008,
)


def _rotl64(value: int, shift: int) -> int:
    return ((value << shift) | (value >> (64 - shift))) & _MASK64 if shift else value


def _keccak_f(state: list[int]) -> None:
    for rc in _RC:
        # theta
        c = [state[x] ^ state[x + 5] ^ state[x + 10] ^ state[x + 15] ^ state[x + 20]
             for x in range(5)]
        d = [c[(x - 1) % 5] ^ _rotl64(c[(x + 1) % 5], 1) for x in range(5)]
        for x in range(5):
            for y in range(5):
                state[x + 5 * y] ^= d[x]
        # rho + pi
        b = [0] * 25
        for x in range(5):
            for y in range(5):
                b[y + 5 * ((2 * x + 3 * y) % 5)] = _rotl64(state[x + 5 * y], _ROT[x][y])
        # chi
        for x in range(5):
            for y in range(5):
                state[x + 5 * y] = b[x + 5 * y] ^ (
                    (~b[(x + 1) % 5 + 5 * y]) & b[(x + 2) % 5 + 5 * y] & _MASK64
                )
        # iota
        state[0] ^= rc


def keccak256(data: bytes) -> bytes:
    """返回 data 的 Keccak-256 摘要（32 字节）。"""
    rate = 136  # 1088-bit rate，512-bit capacity
    padded = bytearray(data)
    padded.append(0x01)  # Keccak 域分隔符（SHA3 为 0x06）
    padded.extend(b"\x00" * ((-len(padded)) % rate))
    padded[-1] |= 0x80

    state = [0] * 25
    for offset in range(0, len(padded), rate):
        block = padded[offset:offset + rate]
        for i in range(rate // 8):
            state[i] ^= int.from_bytes(block[8 * i:8 * i + 8], "little")
        _keccak_f(state)

    out = bytearray()
    for lane in state:
        out.extend(lane.to_bytes(8, "little"))
        if len(out) >= 32:
            break
    return bytes(out[:32])
