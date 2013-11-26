from __future__ import absolute_import

try:
    from corehq.apps.app_manager.tests.test_app_manager import *
    from corehq.apps.app_manager.tests.test_xml_parsing import *
    from corehq.apps.app_manager.tests.test_xform_parsing import *
    from corehq.apps.app_manager.tests.test_form_versioning import *
    from corehq.apps.app_manager.tests.test_success_message import *
    from corehq.apps.app_manager.tests.test_form_preparation_v2 import *
    from corehq.apps.app_manager.tests.test_days_ago_migration import *
    from corehq.apps.app_manager.tests.test_suite import *
    from corehq.apps.app_manager.tests.test_build_errors import *
    from corehq.apps.app_manager.tests.test_views import *
    from corehq.apps.app_manager.tests.test_commcare_settings import *
    from corehq.apps.app_manager.tests.test_brief_view import *
    from .test_get_questions import *
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
