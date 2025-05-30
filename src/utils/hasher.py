import hashlib
import random
import time

_SALT = random.randint(0, 2 ** 32 - 1)
_MASK_63_BIT = 2 ** 63 - 1


def hashMixSalt(string: str) -> int:
    """
    加盐哈希
    :param string:
    :return:
    """
    hasher = hashlib.sha256()
    hasher.update((string + str(_SALT)).encode())
    hashInt = int.from_bytes(hasher.digest(), byteorder='big')
    return hashInt & _MASK_63_BIT


if __name__ == '__main__':
    print(hashMixSalt("test"))
    time.sleep(2)
    print(hashMixSalt("test"))
