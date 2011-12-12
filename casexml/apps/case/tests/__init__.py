from dimagi.utils.logging import log_exception
try:
    from .test_attachments import *
    from .test_bugs import *
    from .test_from_xform import *
    from .test_multi_case_submits import *
    from .test_ota_restore import *
    from .test_v2_parsing import *
except ImportError, e:
    # for some reason the test harness squashes these so log them here for clarity
    # otherwise debugging is a pain
    log_exception(e)
    raise(e)
