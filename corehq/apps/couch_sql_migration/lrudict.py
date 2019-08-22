from __future__ import absolute_import
from __future__ import unicode_literals

import sys
from itertools import islice

_native_dict = sys.version_info[:2] >= (3, 6)
if _native_dict:
    _dict = dict
else:
    from collections import OrderedDict as _dict


class LRUDict(_dict):
    """Least-recently-used dictionary

    Length-limited dictionary that discards least recently "used" items.
    The definition of "used" in this context means accessed with `get`
    or `__getitem__` or set by any mutating method.
    """

    __slots__ = ("max_size",)

    def __init__(self, max_size):
        super(LRUDict, self).__init__()
        self.max_size = max_size

    def __getitem__(self, key):
        if _native_dict:
            value = self.pop(key)
        else:
            value = super(LRUDict, self).__getitem__(key)
            del self[key]
        super(LRUDict, self).__setitem__(key, value)
        return value

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def __setitem__(self, key, value):
        self.pop(key, None)
        super(LRUDict, self).__setitem__(key, value)
        self._lru_trim()

    def setdefault(self, key, default):
        try:
            return self[key]
        except KeyError:
            self[key] = default
            self._lru_trim()
            return default

    def update(self, *args, **kw):
        super(LRUDict, self).update(*args, **kw)
        self._lru_trim()

    def _lru_trim(self):
        discard_n = len(self) - self.max_size
        if discard_n > 0:
            for key in list(islice(self, discard_n)):
                del self[key]

    def copy(self):
        raise NotImplementedError

    @classmethod
    def fromkeys(cls, iterable, value=None):
        raise NotImplementedError

    if not _native_dict:
        # OrderedDict defines these methods in a way that never
        # returns with a mutating __getitem__

        def items(self):
            get = super(LRUDict, self).__getitem__
            return [(key, get(key)) for key in self]

        def iteritems(self):
            get = super(LRUDict, self).__getitem__
            for k in self:
                yield (k, get(k))

        def values(self):
            get = super(LRUDict, self).__getitem__
            return [get(key) for key in self]

        def itervalues(self):
            get = super(LRUDict, self).__getitem__
            for k in self:
                yield get(k)
