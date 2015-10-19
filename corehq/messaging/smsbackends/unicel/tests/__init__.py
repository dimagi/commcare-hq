try:
    from corehq.messaging.smsbackends.unicel.tests.test_create_from_request import *
except ImportError, e:
    # for some reason the test harness squashes these so log them here for clarity
    # otherwise debugging is a pain
    import logging
    logging.exception(e)
    raise
