from unittest.mock import patch

from django.test import SimpleTestCase

from corehq.apps.app_manager.const import REGISTRY_WORKFLOW_SMART_LINK, WORKFLOW_PREVIOUS
from corehq.apps.app_manager.models import (
    Application,
    CaseSearch,
    CaseSearchLabel,
    CaseSearchProperty,
)
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.util.test_utils import flag_enabled


@patch('corehq.apps.app_manager.models.validate_xform', return_value=None)
@patch('corehq.apps.app_manager.helpers.validators.domain_has_privilege', return_value=True)
@patch.object(Application, 'enable_practice_users', return_value=False)
class BuildErrorsInlineSearchTest(SimpleTestCase):

    def test_inline_search_as_parent(self, *args):
        """a parent module and its submodule can not have the same instance_name"""
        factory = AppFactory(build_version='2.51.0')
        m0, _ = factory.new_basic_module('first', 'case')
        m1, _ = factory.new_basic_module('second', 'case', parent_module=m0)

        m0.search_config = CaseSearch(
            search_label=CaseSearchLabel(label={'en': 'Search'}),
            properties=[CaseSearchProperty(name=field) for field in ['name', 'greatest_fear']],
            auto_launch=True,
            inline_search=True,
            instance_name="instance_name"
        )

        m1.search_config = CaseSearch(
            inline_search=True,
            instance_name="instance_name"
        )
        self.assertIn("non-unique instance name with parent module", _get_error_types(factory.app))

    @flag_enabled('DATA_REGISTRY')
    @patch.object(Application, 'supports_data_registry', lambda: True)
    def test_inline_search_smart_links(self, *args):
        factory = AppFactory()
        module, form = factory.new_basic_module('basic', 'person')
        factory.form_requires_case(form, 'person')

        module.search_config = CaseSearch(
            search_label=CaseSearchLabel(label={'en': 'Search'}),
            properties=[CaseSearchProperty(name=field) for field in ['name', 'greatest_fear']],
            data_registry="so_many_cases",
            data_registry_workflow=REGISTRY_WORKFLOW_SMART_LINK,
            auto_launch=True,
            inline_search=True,
        )

        self.assertIn("smart links inline search", _get_error_types(factory.app))

    def test_inline_search_display_only_forms(self, *args):
        """can't use 'display only forms' with inline search"""
        factory = AppFactory(build_version='2.51.0')
        m0, _ = factory.new_basic_module('first', 'case')
        m0.put_in_root = True

        m0.search_config = CaseSearch(
            search_label=CaseSearchLabel(label={'en': 'Search'}),
            properties=[CaseSearchProperty(name=field) for field in ['name', 'greatest_fear']],
            auto_launch=True,
            inline_search=True,
        )

        self.assertIn("inline search to display only forms", _get_error_types(factory.app))

    def test_inline_search_previous_screen(self, *args):
        factory = AppFactory(build_version='2.51.0')
        m0, m0f0 = factory.new_basic_module('first', 'case')
        factory.form_requires_case(m0f0)

        m0.search_config = CaseSearch(
            search_label=CaseSearchLabel(label={'en': 'Search'}),
            properties=[CaseSearchProperty(name=field) for field in ['name', 'greatest_fear']],
            auto_launch=True,
            inline_search=True,
        )
        m0f0.post_form_workflow = WORKFLOW_PREVIOUS

        self.assertIn("workflow previous inline search", _get_error_types(factory.app))


def _get_error_types(app):
    return [error['type'] for error in app.validate_app()]
