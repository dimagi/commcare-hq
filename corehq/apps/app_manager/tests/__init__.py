from __future__ import absolute_import

try:
    from .test_broken_build import *
    from .test_get_questions import *
    from .test_location_xpath import *
    from .test_repeater import *
    from .test_translations import *
    from corehq.apps.app_manager.tests.test_advanced_suite import *
    from corehq.apps.app_manager.tests.test_analytics import *
    from corehq.apps.app_manager.tests.test_app_manager import *
    from corehq.apps.app_manager.tests.test_build_errors import *
    from corehq.apps.app_manager.tests.test_bulk_app_translation import *
    from corehq.apps.app_manager.tests.test_bulk_ui_translation import *
    from corehq.apps.app_manager.tests.test_case_detail_distance import *
    from corehq.apps.app_manager.tests.test_case_list_form import *
    from corehq.apps.app_manager.tests.test_case_list_lookup import *
    from corehq.apps.app_manager.tests.test_case_meta import *
    from corehq.apps.app_manager.tests.test_child_module import *
    from corehq.apps.app_manager.tests.test_commcare_settings import *
    from corehq.apps.app_manager.tests.test_days_ago_migration import *
    from corehq.apps.app_manager.tests.test_dbaccessors import *
    from corehq.apps.app_manager.tests.test_extension_case import *
    from corehq.apps.app_manager.tests.test_form_preparation_v2 import *
    from corehq.apps.app_manager.tests.test_form_versioning import *
    from corehq.apps.app_manager.tests.test_form_workflow import *
    from corehq.apps.app_manager.tests.test_grid_menus import *
    from corehq.apps.app_manager.tests.test_media_suite import *
    from corehq.apps.app_manager.tests.test_models import *
    from corehq.apps.app_manager.tests.test_profile import *
    from corehq.apps.app_manager.tests.test_report_config import *
    from corehq.apps.app_manager.tests.test_report_fixtures_provider import *
    from corehq.apps.app_manager.tests.test_schedule import *
    from corehq.apps.app_manager.tests.test_suite import *
    from corehq.apps.app_manager.tests.test_suite_form_filter_errors import *
    from corehq.apps.app_manager.tests.test_suite_formats import *
    from corehq.apps.app_manager.tests.test_suite_regex import *
    from corehq.apps.app_manager.tests.test_suite_shadow_module import *
    from corehq.apps.app_manager.tests.test_util import *
    from corehq.apps.app_manager.tests.test_views import *
    from corehq.apps.app_manager.tests.test_xform_builder import *
    from corehq.apps.app_manager.tests.test_xform_parsing import *
    from corehq.apps.app_manager.tests.test_xml_parsing import *
    from corehq.apps.app_manager.tests.test_xpath import *
    from corehq.apps.app_manager.xpath_validator.tests import *
except ImportError, e:
    # for some reason the test harness squashes these so log them here for clarity
    # otherwise debugging is a pain
    import logging
    logging.exception(e)
    raise

from corehq.apps.app_manager.models import validate_property, CommentMixin
from corehq.apps.app_manager.util import is_valid_case_type, version_key
from corehq.apps.app_manager.id_strings import _format_to_regex
from corehq.apps.app_manager import xform_builder

__test__ = {
    'is_valid_case_type': is_valid_case_type,
    'version_key': version_key,
    '_format_to_regex': _format_to_regex,
    'validate_property': validate_property,
    'xform_builder': xform_builder,
    'CommentMixinTest': CommentMixin,
}
