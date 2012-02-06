import hashlib
import binascii
from copy import copy


EMPTY_HASH = ""
    
class Checksum(object):
    """
    >>> Checksum(['abc123', '123abc']).hexdigest()
    '409c5c597fa2c2a693b769f0d2ad432b'

    >>> Checksum(['123abc', 'abc123']).hexdigest()
    '409c5c597fa2c2a693b769f0d2ad432b'

    >>> c = Checksum()
    >>> c.add('abc123')
    >>> c.add('123abc')
    >>> c.hexdigest()
    '409c5c597fa2c2a693b769f0d2ad432b'

    >>> Checksum().hexdigest()
    ''

    """

    def __init__(self, init=None):
        self._list = init or []

    def add(self, id):
        self._list.append(id)

    @classmethod
    def hash(cls, line):
        return bytearray([ord(b) for b in hashlib.md5(line).digest()])

    @classmethod
    def xor(cls, bytes1, bytes2):
        assert(len(bytes1) == len(bytes2))
        return bytearray([b1 ^ b2 for (b1, b2) in zip(bytes1, bytes2)])

    def hexdigest(self):
        if not self._list:
            return EMPTY_HASH
        x = copy(self._list)
        x = map(Checksum.hash, x)
        x = reduce(Checksum.xor, x)
        x = binascii.hexlify(str(x))
        return x