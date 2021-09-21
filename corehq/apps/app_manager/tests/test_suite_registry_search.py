from django.test import SimpleTestCase

from corehq.apps.app_manager.models import (
    Application,
    CaseSearch,
    CaseSearchProperty,
    Module,
    AdditionalRegistryQuery,
)
from corehq.apps.app_manager.tests.util import (
    SuiteMixin,
    TestXmlMixin,
    patch_get_xform_resource_overrides,
)
from corehq.apps.builds.models import BuildSpec
from corehq.util.test_utils import flag_enabled

DOMAIN = 'test_domain'


@patch_get_xform_resource_overrides()
class RemoteRequestSuiteTest(SimpleTestCase, TestXmlMixin, SuiteMixin):
    file_path = ('data', 'suite')

    def setUp(self):
        self.app = Application.new_app(DOMAIN, "Untitled Application")
        self.app._id = '123'
        self.app.build_spec = BuildSpec(version='2.35.0', build_number=1)
        self.module = self.app.add_module(Module.new_module("Untitled Module", None))
        self.form = self.app.new_form(0, "Untitled Form", None)
        self.form.requires = 'case'
        self.module.case_type = 'case'

        self.module.search_config = CaseSearch(
            properties=[
                CaseSearchProperty(name='name', label={'en': 'Name'}),
                CaseSearchProperty(name='dob', label={'en': 'Date of birth'})
            ],
        )

        # wrap to have assign_references called
        self.app = Application.wrap(self.app.to_json())
        # reset to newly wrapped module
        self.module = self.app.modules[0]

    @flag_enabled('USH_CASE_CLAIM_UPDATES')
    def test_search_data_registry(self, *args):
        self.module.search_config.data_registry = "myregistry"
        suite = self.app.create_suite()

        expected_entry_query = """
        <partial>
          <query url="http://localhost:8000/a/test_domain/phone/registry_case/123/"
                storage-instance="registry" template="case" default_search="true">
            <data key="case_type" ref="'case'"/>
            <data key="case_id" ref="instance('commcaresession')/session/data/case_id"/>
            <data key="commcare_registry" ref="'myregistry'"/>
          </query>
        </partial>"""
        self.assertXmlPartialEqual(expected_entry_query, suite, "./entry[1]/session/query")

        # assert that session instance is added to the entry
        self.assertXmlHasXpath(suite, "./entry[1]/instance[@id='commcaresession']")

        # assert post is disabled
        self.assertXmlHasXpath(suite, "./remote-request[1]/post[@relevant='false()']")

        expected_data = """
        <partial>
          <data key="commcare_registry" ref="'myregistry'"/>
        </partial>
        """
        self.assertXmlPartialEqual(
            expected_data, suite, "./remote-request[1]/session/query/data[@key='commcare_registry']")

    @flag_enabled('USH_CASE_CLAIM_UPDATES')
    def test_search_data_registry_additional_registry_query(self, *args):
        self.module.search_config.data_registry = "myregistry"
        base_xpath = "instance('registry')/results/case[@case_id=instance('commcaresession')/session/data/case_id]"
        self.module.search_config.additional_registry_queries = [
            AdditionalRegistryQuery(
                instance_name="duplicate",
                case_type_xpath=f"{base_xpath}/potential_duplicate_case_type",
                case_id_xpath=f"{base_xpath}/potential_duplicate_case_id"
            )
        ]
        suite = self.app.create_suite()

        expected_entry_query = f"""
        <partial>
          <query url="http://localhost:8000/a/test_domain/phone/registry_case/123/" storage-instance="duplicate"
                template="case" default_search="true">
            <data key="case_type" ref="{base_xpath}/potential_duplicate_case_type"/>
            <data key="case_id" ref="{base_xpath}/potential_duplicate_case_id"/>
            <data key="commcare_registry" ref="'myregistry'"/>
          </query>
        </partial>"""
        self.assertXmlPartialEqual(expected_entry_query, suite, "./entry[1]/session/query[2]")

        # assert that session and registry instances are added to the entry
        self.assertXmlHasXpath(suite, "./entry[1]/instance[@id='commcaresession']")
        self.assertXmlHasXpath(suite, "./entry[1]/instance[@id='registry']")
