try:
    from .test_case_export import *
    from corehq.apps.reports.tests.test_export_api import *
    from corehq.apps.reports.tests.test_household_verification import *
    from corehq.apps.reports.tests.test_sql_reports import *
    from corehq.apps.reports.tests.test_form_export import *
    from corehq.apps.reports.tests.test_report_api import *
except ImportError, e:
    # for some reason the test harness squashes these so log them here for clarity
    # otherwise debugging is a pain
    import logging
    logging.exception(e)
    raise
