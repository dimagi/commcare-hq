from unittest.mock import patch
from uuid import uuid4

from django.test import SimpleTestCase

from corehq.apps.app_manager.models import (
    CaseSearch,
    CaseSearchLabel,
    CaseSearchProperty,
)
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import (
    TestXmlMixin,
    patch_get_xform_resource_overrides,
)
from corehq.util.test_utils import flag_enabled

from .util import patch_validate_xform


@patch('corehq.util.view_utils.get_url_base', new=lambda: "https://www.example.com")
@patch_validate_xform()
@patch_get_xform_resource_overrides()
@flag_enabled('USH_CASE_LIST_MULTI_SELECT')
class MultiSelectCaseListTests(SimpleTestCase, TestXmlMixin):
    file_path = ('data', 'suite')

    def setUp(self):
        self.factory = AppFactory(domain="multiple-referrals")
        self.app_id = uuid4().hex
        self.factory.app._id = self.app_id
        module, form = self.factory.new_basic_module('basic', 'person')
        self.factory.form_requires_case(form, 'person')

        module.case_details.short.multi_select = True
        module.search_config = CaseSearch(
            search_label=CaseSearchLabel(label={'en': 'Search'}),
            properties=[CaseSearchProperty(name=field) for field in ['name', 'greatest_fear']],
        )
        module.assign_references()

    def test_multi_select_case_list(self):
        self.assertXmlPartialEqual(
            self.get_xml('multi_select_case_list').decode('utf-8').format(app_id=self.factory.app._id),
            self.factory.app.create_suite(),
            "./remote-request",
        )
