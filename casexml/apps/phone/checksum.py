import hashlib
import binascii

class Checksum(object):
    """
    >>> Checksum({'abc123': True, '123abc': False}).hexdigest()
    'c4251c443d45aa2601bf16533fb9dbe1'

    >>> c = Checksum()
    >>> c.add('abc123', open=True)
    >>> c.add('123abc', open=False)
    >>> c.hexdigest()
    'c4251c443d45aa2601bf16533fb9dbe1'

    """
    def __init__(self, init=None):
        self._dict = init or {}

    def add(self, id, open):
        self._dict[id] = open

    @classmethod
    def serialize_entry(cls, entry):
        id, open = entry
        return "%s:%s" % (id, 'o' if open else 'c')

    @classmethod
    def hash(cls, line):
        return bytearray([ord(b) for b in hashlib.md5(line).digest()])

    @classmethod
    def xor(cls, bytes1, bytes2):
        assert(len(bytes1) == len(bytes2))
        return bytearray([b1 ^ b2 for (b1, b2) in zip(bytes1, bytes2)])

    def hexdigest(self):
        x = self._dict.items()
        x = map(Checksum.serialize_entry, x)
        x = map(Checksum.hash, x)
        x = reduce(Checksum.xor, x)
        x = binascii.hexlify(x)
        return x