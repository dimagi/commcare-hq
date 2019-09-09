from collections import namedtuple
import hashlib
import traceback
from django.conf import settings

from corehq.util.cache_utils import ExponentialBackoff


def is_hard_mode():
    """Check if soft assert is in hard mode (true when testing)

    Use `corehq.util.test_utils.softer_assert` to override in tests
    """
    return settings.UNIT_TESTING

SoftAssertInfo = namedtuple('SoftAssertInfo',
                            ['traceback', 'count', 'msg', 'key', 'line',
                             'short_traceback', 'obj'])


class SoftAssert(object):

    def __init__(self, debug=False, send=None, use_exponential_backoff=True,
                 skip_frames=0, key_limit=2):
        assert send
        self.debug = debug
        self.send = send
        self.use_exponential_backoff = use_exponential_backoff
        self.tb_skip = skip_frames + 3
        self.key_limit = key_limit

    def __call__(self, assertion, msg=None, obj=None):
        return self._call(assertion, msg, obj)

    call = __call__

    def _call(self, assertion, msg=None, obj=None):
        """
        assertion: what we're asserting
        msg: a static message describing the error
        obj: the specific piece of data, if any, that tripped the assertion

        returns the assertion itself
        """
        if not assertion:
            if self.debug or is_hard_mode():
                raise AssertionError(msg)
            short_tb = get_traceback(skip=self.tb_skip, limit=self.key_limit)
            full_tb = get_traceback(skip=self.tb_skip)
            line = short_tb.strip().split('\n')[-1].strip()
            tb_id = hashlib.md5(short_tb.encode('utf-8')).hexdigest()
            count = ExponentialBackoff.increment(tb_id)
            if not self.use_exponential_backoff or not ExponentialBackoff.should_backoff(tb_id):
                if msg:
                    msg = msg.replace('\n', '\\n')
                self.send(SoftAssertInfo(traceback=full_tb,
                                         short_traceback=short_tb,
                                         count=count,
                                         msg=msg,
                                         key=tb_id, line=line, obj=obj))
        return assertion


def get_traceback(skip=0, limit=None):
    if limit:
        total_limit = skip + limit
    else:
        total_limit = None
    stack = traceback.extract_stack(limit=total_limit)
    if skip:
        stack = stack[:-skip]
    if limit:
        stack = stack[-limit:]
    return ''.join(traceback.format_list(stack))
