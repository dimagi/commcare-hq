import hashlib
from datetime import datetime

def to_number(bytes):
    return reduce(lambda a, b: a*256 + b, bytes)

def to_base(n, b):
    if not n:
        return []
    else:
        rest, digit = divmod(n, b)
        answer = to_base(rest, b)
        answer.append(digit)
        return answer

class DeidGenerator(object):

    def __init__(self, seed, salt, bytes=8):
        assert(bytes < 20)
        self.seed = "%s:%s" % (seed, salt)
        self.bytes = bytes
        self.number = self._get_number()

    def _get_number(self):
        return to_number(self._sha1_bytes())

    def _sha1_bytes(self):
        byte_list = hashlib.sha1(self.seed).digest()
        for b in byte_list[:self.bytes]:
            yield ord(b)

    def digest(self, alphabet="0123456789"):
        b = len(alphabet)
        answer = map(lambda i: alphabet[i], to_base(self.number, b))
        if isinstance(alphabet, basestring):
            answer = ''.join(answer)
        return answer

    def random_hash(self):
        """Generate a 'random' hash of 10 alphanumerics (ALL CAPS)"""
        id = self.digest("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ")[-10:]
        while len(id) < 10:
            id = "0" + id
        return id

    def random_number(self, low, high):
        """Generate a 'random' number such that low <= n < high"""
        return self.digest(range(low, high))[-1]
