from dimagi.utils.logging import log_exception
try:
    from casexml.apps.phone.tests.test_ota_restore import *
    from casexml.apps.phone.tests.test_sync_token_updates import *
except ImportError, e:
    # for some reason the test harness squashes these so log them here for clarity
    # otherwise debugging is a pain
    log_exception(e)
    raise(e)
