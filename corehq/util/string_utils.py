import random
import six
import string


def random_string(n=6):
    # http://stackoverflow.com/a/23728630/835696
    return ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(n))


def ensure_unicode(s):
    if isinstance(s, six.text_type):
        return s
    elif isinstance(s, six.binary_type):
        return s.decode('utf-8')
    return six.text_type(s)
