from dimagi.utils.logging import log_exception
try:
    from corehq.apps.hqcase.tests.test_force_close import *
    from corehq.apps.hqcase.tests.test_case_sharing import *
    from corehq.apps.hqcase.tests.test_pillows import *
except ImportError, e:
    # for some reason the test harness squashes these so log them here for clarity
    # otherwise debugging is a pain
    log_exception(e)
    raise(e)
