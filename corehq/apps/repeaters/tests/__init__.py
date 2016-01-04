import logging

try:
    from .test_repeater import *
except ImportError, e:
    # for some reason the test harness squashes these so log them here for clarity
    # otherwise debugging is a pain
    logging.exception(e)
    raise
