from __future__ import absolute_import

try:
    from .test_app_manager import *
    from .test_xml_parsing import *
    from .test_xform_parsing import *
    from .test_success_message import *
    from .test_form_preparation_v2 import *
    from .test_days_ago_migration import *
    from .test_suite import *
    from .test_build_errors import *
    from .test_views import *
    from .test_commcare_settings import *
    from .test_brief_view import *
    from .test_get_questions import *
    from .test_case_properties import *
    from .test_repeater import *
except ImportError, e:
    # for some reason the test harness squashes these so log them here for clarity
    # otherwise debugging is a pain
    import logging
    logging.exception(e)
    raise

from corehq.apps.app_manager.util import is_valid_case_type
__test__ = {
    'is_valid_case_type': is_valid_case_type
}
