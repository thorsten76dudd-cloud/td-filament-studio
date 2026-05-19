"""Creality CFS MIFARE Classic encryption (reverse-engineered, community)."""

from Crypto.Cipher import AES

KEY_DEFAULT = bytes([0xFF] * 6)

_MASTER_KEY = bytes(
    [72, 64, 67, 70, 107, 82, 110, 122, 64, 75, 65, 116, 66, 74, 112, 50]
)
_UID_KEY = bytes(
    [113, 51, 98, 117, 94, 116, 49, 110, 113, 102, 90, 40, 112, 102, 36, 49]
)


def create_tag_key(uid: bytes) -> bytes:
    if len(uid) < 4:
        return KEY_DEFAULT
    plain = bytearray(16)
    x = 0
    for i in range(16):
        if x >= 4:
            x = 0
        plain[i] = uid[x]
        x += 1
    cipher = AES.new(_UID_KEY, AES.MODE_ECB)
    return cipher.encrypt(bytes(plain))[:6]


def cipher_data(mode: int, data: bytes) -> bytes:
    cipher = AES.new(_MASTER_KEY, AES.MODE_ECB)
    if mode == 1:
        return cipher.encrypt(data)
    return cipher.decrypt(data)
