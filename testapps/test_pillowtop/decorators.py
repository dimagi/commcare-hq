import functools
from django.conf import settings
import sys

global TESTS_ALLOWED
TESTS_ALLOWED = False


def require_explicit_elasticsearch_testing(fn):
    """
    This decorator is here to make it hard for developers to delete their real elasticsearch
    indices.
    """
    @functools.wraps(fn)
    def decorated(*args, **kwargs):
        assert settings.UNIT_TESTING, 'You can only run this function in unit testing mode.'
        global TESTS_ALLOWED
        if not TESTS_ALLOWED and not getattr(settings, 'ALLOW_ELASTICSEARCH_TESTS', False):
            should_proceed = raw_input(
                'Are you sure you want to run ElasticSearch tests?? '
                'These may WIPE all the REAL indices on your computer?? (y/n)\n'
                'NOTE: set ALLOW_ELASTICSEARCH_TESTS=True in your localsettings to disable this warning.\n'
            ).lower()
            if should_proceed != 'y':
                print 'Tests aborted!'
                sys.exit()
            else:
                TESTS_ALLOWED = True
        return fn(*args, **kwargs)
    return decorated
