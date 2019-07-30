from __future__ import absolute_import
from __future__ import unicode_literals
import hashlib
import binascii
from copy import copy
import six
from six.moves import zip
from functools import reduce
from six.moves import map


EMPTY_HASH = ""
CASE_STATE_HASH_PREFIX = "ccsh"


class CaseStateHash(object):
    
    def __init__(self, hash):
        self.hash = hash
    
    @classmethod
    def parse(cls, str):
        assert str.lower().startswith("%s:" % CASE_STATE_HASH_PREFIX)
        return cls(str[len(CASE_STATE_HASH_PREFIX) + 1:])
    
    def __str__(self):
        return "%s:%s" % (CASE_STATE_HASH_PREFIX, self.hash)
    
    def __eq__(self, obj):
        return isinstance(obj, CaseStateHash) and obj.hash == self.hash 
    
    def __ne__(self, obj):
        return not self == obj

    __hash__ = None
        

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
        if isinstance(line, six.text_type):
            line = line.encode('utf-8')
        return bytearray(hashlib.md5(line).digest())

    @classmethod
    def xor(cls, bytes1, bytes2):
        assert(len(bytes1) == len(bytes2))
        return bytearray([b1 ^ b2 for (b1, b2) in zip(bytes1, bytes2)])

    def hexdigest(self):
        if not self._list:
            return EMPTY_HASH
        x = copy(self._list)
        x = list(map(Checksum.hash, x))
        x = reduce(Checksum.xor, x)
        x = binascii.hexlify(bytes(x)).decode('utf-8')
        return x
