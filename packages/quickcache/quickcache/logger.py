import logging


logger = logging.getLogger('quickcache')


def assert_function(assertion, message):
    if assertion:
        logger.warn(message)
