import logging
try:
    from couchforms.tests.test_meta import *
    from couchforms.tests.test_duplicates import *
    from couchforms.tests.test_edits import *
except ImportError, e:
    # for some reason the test harness squashes these so log them here for clarity
    # otherwise debugging is a pain
    logging.error(e)
    raise(e)
