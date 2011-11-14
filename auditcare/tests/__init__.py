import logging
try:
    from auditcare.tests.auth import *
    from auditcare.tests.modelevents import *
except ImportError, e:
    # for some reason the test harness squashes these so log them here for clarity
    # otherwise debugging is a pain
    logging.error(e)
    raise(e)
