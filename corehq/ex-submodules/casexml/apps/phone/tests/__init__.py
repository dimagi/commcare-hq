import logging
try:
    from .test_ota_restore import *
    from .test_state_hash import *
    from .test_sync_logs import *
    from .test_sync_mode import *
except ImportError, e:
    # for some reason the test harness squashes these so log them here for clarity
    # otherwise debugging is a pain
    logging.exception(str(e))
    raise

# doctest
from casexml.apps.phone.checksum import Checksum
__test__ = {
    'checksum': Checksum
}