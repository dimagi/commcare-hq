from collections import namedtuple
import hashlib
import traceback


SoftAssertInfo = namedtuple('SoftAssertInfo',
                            ['traceback', 'count', 'msg', 'key', 'line',
                             'short_traceback'])


class SoftAssert(object):
    def __init__(self, debug=False, send=None, incrementing_counter=None,
                 should_send=None, tb_skip=2, key_limit=2):
        assert send
        assert incrementing_counter
        assert should_send
        self.debug = debug
        self.send = send
        self.incrementing_counter = incrementing_counter
        self.should_send = should_send
        self.tb_skip = tb_skip
        self.key_limit = key_limit

    def __call__(self, assertion, msg=None):
        if not assertion:
            if self.debug:
                raise AssertionError(msg)
            short_tb = get_traceback(skip=self.tb_skip, limit=self.key_limit)
            full_tb = get_traceback(skip=self.tb_skip)
            line = short_tb.strip().split('\n')[-1].strip()
            tb_id = hashlib.md5(short_tb).hexdigest()
            count = self.incrementing_counter(tb_id)
            if self.should_send(count):
                self.send(SoftAssertInfo(traceback=full_tb,
                                         short_traceback=short_tb,
                                         count=count,
                                         msg=msg,
                                         key=tb_id, line=line))
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
