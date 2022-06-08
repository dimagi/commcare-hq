from unittest.mock import patch

from django.test import SimpleTestCase

from corehq.apps.app_manager.const import REGISTRY_WORKFLOW_SMART_LINK
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
@patch('corehq.apps.builds.models.BuildSpec.supports_j2me', return_value=False)
@patch.object(Application, 'enable_practice_users', return_value=False)
class BuildErrorsInlineSearchTest(SimpleTestCase):

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


def _get_error_types(app):
    return [error['type'] for error in app.validate_app()]
