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
        try:
            return s.decode('utf-8')
        except UnicodeDecodeError:
            # https://sentry.io/dimagi/commcarehq/issues/391378081/
            return s.decode('latin1')
    return six.text_type(s)
