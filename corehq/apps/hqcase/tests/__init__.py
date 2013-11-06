from dimagi.utils.logging import log_exception
try:
    from .test_bugs import *
    from .test_case_assigment import *
    from .test_force_close import *
    from .test_case_sharing import *
    from .test_object_cache import *
except ImportError, e:
    # for some reason the test harness squashes these so log them here for clarity
    # otherwise debugging is a pain
    log_exception(e)
    raise(e)
