import logging
try:
    from .test_formdata import *
    from .test_casedata import *
except ImportError, e:
    # for some reason the test harness squashes these so log them here for clarity
    # otherwise debugging is a pain
    logging.error(e)
    raise(e)
