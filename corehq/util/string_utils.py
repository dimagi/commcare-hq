from __future__ import absolute_import
from __future__ import unicode_literals
import binascii
import random
import string
import six
from six.moves import range


def random_string(n=6):
    # http://stackoverflow.com/a/23728630/835696
    return ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(n))


def ensure_unicode(s):
    if not s or isinstance(s, six.text_type):
        return s
    else:
        return s.decode('utf-8')


def confirm_ascii(s):
    """
    If s can be represented in ascii, returns s untouched.
    Otherwise, raises a UnicodeEncodeError.
    Compatible with both Python 2 and 3.
    """
    s.encode('ascii')
    return s


def to_utf_16_be(s):
    """
    Converts s to a string hex representation using utf-16 big endian encoding.
    Compatible with both Python 2 and 3.
    """
    return binascii.hexlify(s.encode('utf_16_be')).decode('ascii').upper()
