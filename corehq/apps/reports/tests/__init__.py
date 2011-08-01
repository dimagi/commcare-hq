try:
    from corehq.apps.reports.tests.test_export_api import *
    from corehq.apps.reports.tests.test_household_verification import *
    from corehq.apps.reports.tests.test_submissions_by_form import *
except ImportError, e:
    # for some reason the test harness squashes these so log them here for clarity
    # otherwise debugging is a pain
    import logging
    logging.exception(e)
    raise
