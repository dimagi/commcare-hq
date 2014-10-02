from __future__ import absolute_import

try:
    from corehq.apps.export.tests.export_file_validations import *
except ImportError, e:
    # for some reason the test harness squashes these so log them here for clarity
    # otherwise debugging is a pain
    import logging
    logging.exception(e)
    raise
