from __future__ import absolute_import
from builtins import range
import random
import string
import six


def random_string(n=6):
    # http://stackoverflow.com/a/23728630/835696
    return ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(n))


def ensure_unicode(s):
    if not s or isinstance(s, six.text_type):
        return s
    else:
        return s.decode('utf-8')
