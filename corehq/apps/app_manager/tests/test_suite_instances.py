from unittest import mock

from django.test import SimpleTestCase

from corehq.apps.app_manager.exceptions import (
    DuplicateInstanceIdError,
    UnknownInstanceError,
)
from corehq.apps.app_manager.models import (
    CaseSearch,
    CaseSearchProperty,
    CustomInstance,
    DefaultCaseSearchProperty,
    Itemset,
    ShadowModule,
)
from corehq.apps.app_manager.suite_xml.post_process.instances import (
    get_instance_names,
)
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import (
    SuiteMixin,
    patch_get_xform_resource_overrides,
)
from corehq.apps.locations.models import LocationFixtureConfiguration
from corehq.util.test_utils import flag_enabled, generate_cases


@patch_get_xform_resource_overrides()
class SuiteInstanceTests(SimpleTestCase, SuiteMixin):
    file_path = ('data', 'suite')

    def setUp(self):
        super().setUp()
        self.factory = AppFactory(include_xmlns=True)
        self.module, self.form = self.factory.new_basic_module('m0', 'case1')

    def test_custom_instances(self):
        instance_id = "foo"
        instance_path = "jr://foo/bar"
        self.form.custom_instances = [CustomInstance(instance_id=instance_id, instance_path=instance_path)]
        self.assertXmlPartialEqual(
            """
            <partial>
                <instance id='{}' src='{}' />
            </partial>
            """.format(instance_id, instance_path),
            self.factory.app.create_suite(),
            "entry/instance"
        )

    def test_unknown_instances(self):
        xpath = "instance('unknown')/thing/val = 1"
        self.form.form_filter = xpath
        with self.assertRaises(UnknownInstanceError) as e:
            self.factory.app.create_suite()
        self.assertIn(xpath, str(e.exception))

    def test_duplicate_custom_instances(self):
        self.factory.form_requires_case(self.form)
        instance_id = "casedb"
        instance_path = "jr://casedb/bar"
        # Use form_filter to add instances
        self.form.form_filter = "count(instance('casedb')/casedb/case[@case_id='123']) > 0"
        self.form.custom_instances = [CustomInstance(instance_id=instance_id, instance_path=instance_path)]
        with self.assertRaises(DuplicateInstanceIdError):
            self.factory.app.create_suite()

    def test_duplicate_regular_instances(self):
        """Make sure instances aren't getting added multiple times if they are referenced multiple times
        """
        self.factory.form_requires_case(self.form)
        self.form.form_filter = "instance('casedb') instance('casedb') instance('locations') instance('locations')"
        self.assertXmlPartialEqual(
            """
            <partial>
                <instance id='casedb' src='jr://instance/casedb' />
                <instance id='locations' src='jr://fixture/locations' />
            </partial>
            """,
            self.factory.app.create_suite(),
            "entry/instance"
        )

    def test_location_instances(self):
        self.form.form_filter = "instance('locations')/locations/"
        self.factory.new_form(self.module)
        suite = self.factory.app.create_suite()
        self.assertXmlPartialEqual(
            """
            <partial>
                <instance id='locations' src='jr://fixture/locations' />
            </partial>
            """,
            suite,
            "entry[1]/instance"
        )
        self.assertXmlPartialEqual("<partial />", suite, "entry[2]/instance")

    @mock.patch.object(LocationFixtureConfiguration, 'for_domain')
    def test_location_instance_during_migration(self, sync_patch):
        # tests for expectations during migration from hierarchical to flat location fixture
        # Domains with HIERARCHICAL_LOCATION_FIXTURE enabled and with sync_flat_fixture set to False
        # should have hierarchical jr://fixture/commtrack:locations fixture format
        # All other cases to have flat jr://fixture/locations fixture format
        self.form.form_filter = "instance('locations')/locations/"
        configuration_mock_obj = mock.MagicMock()
        sync_patch.return_value = configuration_mock_obj

        hierarchical_fixture_format_xml = """
            <partial>
                <instance id='locations' src='jr://fixture/commtrack:locations' />
            </partial>
        """

        flat_fixture_format_xml = """
            <partial>
                <instance id='locations' src='jr://fixture/locations' />
            </partial>
        """

        configuration_mock_obj.sync_flat_fixture = True  # default value
        # Domains migrating to flat location fixture, will have FF enabled and should successfully be able to
        # switch between hierarchical and flat fixture
        with flag_enabled('HIERARCHICAL_LOCATION_FIXTURE'):
            configuration_mock_obj.sync_hierarchical_fixture = True  # default value
            self.assertXmlPartialEqual(flat_fixture_format_xml,
                                       self.factory.app.create_suite(), "entry/instance")

            configuration_mock_obj.sync_hierarchical_fixture = False
            self.assertXmlPartialEqual(flat_fixture_format_xml,
                                       self.factory.app.create_suite(), "entry/instance")

            configuration_mock_obj.sync_flat_fixture = False
            self.assertXmlPartialEqual(hierarchical_fixture_format_xml,
                                       self.factory.app.create_suite(), "entry/instance")

            configuration_mock_obj.sync_hierarchical_fixture = True
            self.assertXmlPartialEqual(hierarchical_fixture_format_xml,
                                       self.factory.app.create_suite(), "entry/instance")

        # To ensure for new domains or domains adding locations now come on flat fixture
        configuration_mock_obj.sync_hierarchical_fixture = True  # default value
        self.assertXmlPartialEqual(flat_fixture_format_xml, self.factory.app.create_suite(), "entry/instance")

        # This should not happen ideally since the conf can not be set without having HIERARCHICAL_LOCATION_FIXTURE
        # enabled. Considering that a domain has sync hierarchical fixture set to False without the FF
        # HIERARCHICAL_LOCATION_FIXTURE. In such case the domain stays on flat fixture format
        configuration_mock_obj.sync_hierarchical_fixture = False
        self.assertXmlPartialEqual(flat_fixture_format_xml, self.factory.app.create_suite(), "entry/instance")

    def test_unicode_lookup_table_instance(self):
        self.form.form_filter = "instance('item-list:província')/província/"
        self.assertXmlPartialEqual(
            """
            <partial>
                <instance id='item-list:província' src='jr://fixture/item-list:província' />
            </partial>
            """,
            self.factory.app.create_suite(),
            "entry/instance"
        )

    def test_search_input_instance(self):
        # instance is not added and no errors
        self.form.form_filter = "instance('search-input:results')/values/"
        self.assertXmlPartialEqual(
            """
            <partial>
            <instance id="search-input:results" src="jr://instance/search-input/results"/>
            </partial>
            """,
            self.factory.app.create_suite(),
            "entry/instance"
        )

    def test_search_input_instance_remote_request(self):
        self.form.requires = 'case'
        self.module.case_type = 'case'

        self.module.search_config = CaseSearch(
            properties=[
                CaseSearchProperty(name='name', label={'en': 'Name'}),
            ],
            default_properties=[
                DefaultCaseSearchProperty(
                    property="_xpath_query",
                    defaultValue="instance('search-input:results')/input/field[@name = 'first_name']"
                )
            ]
        )
        self.module.assign_references()
        self.assertXmlPartialEqual(
            # 'search-input' instance ignored
            """
            <partial>
                <instance id="casedb" src="jr://instance/casedb"/>
            </partial>
            """,
            self.factory.app.create_suite(),
            "entry/instance"
        )

    def test_shadow_module_custom_instances(self):
        instance_id = "foo"
        instance_path = "jr://foo/bar"
        self.form.custom_instances = [CustomInstance(instance_id=instance_id, instance_path=instance_path)]

        shadow_module = self.factory.app.add_module(ShadowModule.new_module("shadow", "en"))
        shadow_module.source_module_id = self.module.get_or_create_unique_id()

        self.assertXmlPartialEqual(
            """
            <partial>
                <instance id='{}' src='{}' />
            </partial>
            """.format(instance_id, instance_path),
            self.factory.app.create_suite(),
            "entry[2]/instance"
        )

    def test_search_prompt_itemset_instance(self):
        self._test_search_prompt_itemset_instance(self.module)

    def test_shadow_module_search_prompt_itemset_instance(self):
        shadow_module = self.factory.app.add_module(ShadowModule.new_module("shadow", "en"))
        shadow_module.source_module_id = self.module.get_or_create_unique_id()
        self._test_search_prompt_itemset_instance(shadow_module)

    def _test_search_prompt_itemset_instance(self, module):
        instance_id = "item-list:123"
        module.search_config = CaseSearch(
            properties=[
                CaseSearchProperty(name='name', label={'en': 'Name'}, input_="select1", itemset=Itemset(
                    instance_id=instance_id,
                    nodeset=f"instance('{instance_id}')/rows/row",
                    label='name',
                    value='id',
                    sort='id',
                )),
            ],
        )
        module.assign_references()
        suite = self.factory.app.create_suite()

        expected_instance = f"""
                <partial>
                  <instance id="{instance_id}" src="jr://fixture/item-list:123"/>
                </partial>
                """
        self.assertXmlPartialEqual(
            expected_instance,
            suite,
            f"./remote-request[1]/instance[@id='{instance_id}']",
        )

    def test_module_filter_instances_on_all_forms(self):
        # instances from module filters result in instance declarations in all forms in the module
        factory = AppFactory(build_version='2.20.0')  # enable_module_filtering
        self.module, self.form = factory.new_basic_module('m0', 'case1')
        self.module.module_filter = "instance('locations')/locations/"
        factory.new_form(self.module)

        suite = factory.app.create_suite()
        instance_xml = "<partial><instance id='locations' src='jr://fixture/locations' /></partial>"
        self.assertXmlPartialEqual(instance_xml, suite, "entry/command[@id='m0-f0']/../instance")
        self.assertXmlPartialEqual(instance_xml, suite, "entry/command[@id='m0-f1']/../instance")

    def test_module_filter_instances_on_all_forms_merged_modules(self):
        # instances from module filters result in instance declarations in all forms in the module
        # and if two modules are display_in_root, then on forms in the other module too
        factory = AppFactory(build_version='2.20.0')  # enable_module_filtering
        self.m0, self.m0f0 = factory.new_basic_module('m0', 'case1')
        self.m0.module_filter = "instance('groups')/groups/"
        self.m0.put_in_root = True

        self.m1, self.m1f0 = factory.new_basic_module('m1', 'case1')
        self.m1.module_filter = "instance('locations')/locations/"
        self.m1.put_in_root = True

        suite = factory.app.create_suite()
        instance_xml = """<partial>
            <instance id='groups' src='jr://fixture/user-groups' />
            <instance id='locations' src='jr://fixture/locations' />
        </partial>"""
        self.assertXmlPartialEqual(instance_xml, suite, "entry/command[@id='m0-f0']/../instance")
        self.assertXmlPartialEqual(instance_xml, suite, "entry/command[@id='m1-f0']/../instance")


@generate_cases([
    ("instance('test')/rows/row", {"test"}),
    ("instance('test')/rows/row/0 != instance('test')/rows/row/1", {"test"}),
    ("instance('one')/rows/row/0 != instance('two')/rows/row/1", {"one", "two"}),
    ("instance( 'test' )/something", {"test"}),
    ("""instance(
        'search-input:results'
    )/input/field[@name = 'first_name']""", {"search-input:results"}),
], SuiteInstanceTests)
def test_get_instance_names(self, xpath, expected_names):
    self.assertEqual(get_instance_names(xpath), expected_names)
