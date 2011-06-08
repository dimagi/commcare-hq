from dimagi.utils.logging import log_exception
try:
    from casexml.apps.case.tests.test_from_xform import *
    from casexml.apps.case.tests.test_multi_case_submits import *
    from casexml.apps.case.tests.test_attachments import *
    from casexml.apps.case.tests.test_bugs import *
except ImportError, e:
    # for some reason the test harness squashes these so log them here for clarity
    # otherwise debugging is a pain
    log_exception(e)
    raise(e)
