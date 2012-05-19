from dimagi.utils.logging import log_exception
try:
    from .test_repeater import *
    from .test_submissions import *
    from .test_submit_errors import *
    from .test_url_regex import *
except ImportError, e:
    # for some reason the test harness squashes these so log them here for clarity
    # otherwise debugging is a pain
    log_exception(e)
    raise(e)
