from __future__ import absolute_import
import logging
import logging.handlers

def initialize_logging(loginitfunc):
    """call in settings.py after importing localsettings to initialize logging.
    ensures that logging is only initialized once. 'loginitfunc' actually does
    the initialization"""
    if not hasattr(logging, '_initialized'):
        loginitfunc()
        logging.info('logging initialized')
        logging._initialized = True

def default_logging(logfile):
    """standard logging configuration useful for development. this should be
    the default argument passed to initialize_logging in settings.py. it should
    be overridden with a different function in localsettings.py when in a
    deployment environment"""
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    handlers = [
        logging.StreamHandler(),
        logging.handlers.RotatingFileHandler(logfile, maxBytes=2**24, backupCount=3),
    ]

    for handler in handlers:
        handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(message)s'))
        root.addHandler(handler)

from dimagi.utils.repo import get_revision
