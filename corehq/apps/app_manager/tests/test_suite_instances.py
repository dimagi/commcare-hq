from unittest import mock

from django.test import SimpleTestCase

from corehq.apps.app_manager.exceptions import DuplicateInstanceIdError
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.models import CustomInstance
from corehq.apps.app_manager.tests.util import (
    SuiteMixin,
    TestXmlMixin,
    patch_get_xform_resource_overrides,
)
from corehq.apps.locations.models import LocationFixtureConfiguration
from corehq.util.test_utils import flag_enabled


@patch_get_xform_resource_overrides()
class SuiteInstanceTests(SimpleTestCase, TestXmlMixin, SuiteMixin):
    file_path = ('data', 'suite')

    def setUp(self):
        super().setUp()
        self.factory = AppFactory(include_xmlns=True)
        self.module, self.form = self.factory.new_basic_module('m0', 'case1')

    def test_custom_instances(self, *args):
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

    def test_duplicate_custom_instances(self, *args):
        self.factory.form_requires_case(self.form)
        instance_id = "casedb"
        instance_path = "jr://casedb/bar"
        # Use form_filter to add instances
        self.form.form_filter = "count(instance('casedb')/casedb/case[@case_id='123']) > 0"
        self.form.custom_instances = [CustomInstance(instance_id=instance_id, instance_path=instance_path)]
        with self.assertRaises(DuplicateInstanceIdError):
            self.factory.app.create_suite()

    def test_duplicate_regular_instances(self, *args):
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

    def test_location_instances(self, *args):
        self.form.form_filter = "instance('locations')/locations/"
        self.assertXmlPartialEqual(
            """
            <partial>
                <instance id='locations' src='jr://fixture/locations' />
            </partial>
            """,
            self.factory.app.create_suite(),
            "entry/instance"
        )

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
            self.assertXmlPartialEqual(flat_fixture_format_xml, self.factory.app.create_suite(), "entry/instance")

            configuration_mock_obj.sync_flat_fixture = False
            self.assertXmlPartialEqual(hierarchical_fixture_format_xml, self.factory.app.create_suite(), "entry/instance")

            configuration_mock_obj.sync_hierarchical_fixture = True
            self.assertXmlPartialEqual(hierarchical_fixture_format_xml, self.factory.app.create_suite(), "entry/instance")

        # To ensure for new domains or domains adding locations now come on flat fixture
        configuration_mock_obj.sync_hierarchical_fixture = True  # default value
        self.assertXmlPartialEqual(flat_fixture_format_xml, self.factory.app.create_suite(), "entry/instance")

        # This should not happen ideally since the conf can not be set without having HIERARCHICAL_LOCATION_FIXTURE
        # enabled. Considering that a domain has sync hierarchical fixture set to False without the FF
        # HIERARCHICAL_LOCATION_FIXTURE. In such case the domain stays on flat fixture format
        configuration_mock_obj.sync_hierarchical_fixture = False
        self.assertXmlPartialEqual(flat_fixture_format_xml, self.factory.app.create_suite(), "entry/instance")

    def test_unicode_lookup_table_instance(self, *args):
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
