try:
    from .test_analytics import *
    from .test_case_export import *
    from .test_cache import *
    from .test_data_sources import *
    from .test_daterange import *
    from .test_dbaccessors import *
    from .test_esaccessors import *
    from .test_export_api import *
    from .test_form_export import *
    from .test_generic import *
    from .test_filters import *
    from .test_ledgers_by_location import *
    from .test_pillows_cases import *
    from .test_pillows_xforms import *
    from .test_readable_formdata import *
    from .test_report_api import *
    from .test_scheduled_reports import *
    from .test_sql_reports import *
    from .test_time_and_date_manipulations import *
    from .test_util import *
except ImportError, e:
    # for some reason the test harness squashes these so log them here for clarity
    # otherwise debugging is a pain
    import logging
    logging.exception(e)
    raise
