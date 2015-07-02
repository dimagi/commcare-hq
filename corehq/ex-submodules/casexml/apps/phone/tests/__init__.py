import logging
try:
    from .test_cleanliness import *
    from .test_new_sync import *
    from .test_index_tree import *
    from .test_ota_restore import *
    from .test_ota_restore_v3 import *
    from .test_state_hash import *
    from .test_sync_logs import *
    from .test_sync_mode import *
    from .test_batched_mode import BatchRestoreTests
    from .test_ota_fixtures import OtaFixtureTest
    # uncomment to run performance tests
    # from .performance_tests import SyncPerformanceTest
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
