from __future__ import absolute_import
import sys
import traceback
import logging

LOG_LEVELS = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG
}


def get_log_level(level):
    return LOG_LEVELS.get(level, logging.INFO)
    
def set_log_level(level):
    loglevel = LOG_LEVELS.get(level, logging.INFO)
    logging.basicConfig(level=loglevel)
    
def log_exception(e):
    """Log an exception, with a stacktrace"""
    type, value, tb = sys.exc_info()
    traceback_string = "".join(traceback.format_tb(tb))
    logging.error(e)
    logging.error(traceback_string)
