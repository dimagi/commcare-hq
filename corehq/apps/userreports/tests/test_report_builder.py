from django.test import TestCase

from unittest.mock import patch

from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.data_dictionary.models import CaseType, CaseProperty
from corehq.apps.domain.shortcuts import create_user
from corehq.apps.registry.schema import RegistrySchemaBuilder
from corehq.apps.registry.tests.utils import create_registry_for_test, Invitation
from corehq.apps.userreports.app_manager.data_source_meta import (
    DATA_SOURCE_TYPE_CASE,
    DATA_SOURCE_TYPE_FORM,
    DATA_SOURCE_TYPE_RAW,
)
from corehq.apps.userreports.app_manager.helpers import (
    get_case_data_source,
    get_form_data_source,
)
from corehq.apps.userreports.dbaccessors import delete_all_report_configs
from corehq.apps.userreports.models import (
    DataSourceConfiguration,
    ReportConfiguration,
)
from corehq.apps.userreports.reports.builder.columns import (
    MultiselectQuestionColumnOption,
)
from corehq.apps.userreports.reports.builder.const import (
    COMPUTED_OWNER_LOCATION_PROPERTY_ID,
    COMPUTED_OWNER_LOCATION_WITH_DESENDANTS_PROPERTY_ID,
    COMPUTED_OWNER_LOCATION_ARCHIVED_WITH_DESCENDANTS_PROPERTY_ID,
)
from corehq.apps.userreports.reports.builder.forms import (
    ConfigureListReportForm,
    ConfigureTableReportForm,
    UnmanagedDataSourceHelper,
    ApplicationFormDataSourceHelper,
    ApplicationCaseDataSourceHelper,
    RegistryCaseDataSourceHelper,
)
from corehq.apps.userreports.tests.utils import get_simple_xform, get_sample_registry_data_source
from corehq.util.test_utils import flag_enabled


class ReportBuilderDBTest(TestCase):
    domain = 'domain'
    case_type = 'report_builder_case_type'

    @classmethod
    def setUpClass(cls):
        super(ReportBuilderDBTest, cls).setUpClass()
        factory = AppFactory(domain=cls.domain)
        module, form = factory.new_basic_module('Untitled Module', cls.case_type)
        form.source = get_simple_xform()
        cls.form = form
        factory.form_requires_case(form, case_type=cls.case_type, update={
            'first_name': '/data/first_name',
            'last_name': '/data/last_name',
        })
        cls.app = factory.app
        cls.app.save()

    @classmethod
    def tearDownClass(cls):
        cls.app.delete()
        for config in DataSourceConfiguration.all():
            config.delete()
        delete_all_report_configs()
        super(ReportBuilderDBTest, cls).tearDownClass()


class DataSourceBuilderTest(ReportBuilderDBTest):

    def test_builder_bad_type(self):
        with self.assertRaises(AssertionError):
            ApplicationFormDataSourceHelper(self.domain, self.app, 'case', self.form.unique_id)

    def test_builder_bad_type_case(self):
        with self.assertRaises(AssertionError):
            ApplicationCaseDataSourceHelper(self.domain, self.app, 'form', self.form.unique_id)

    def test_builder_for_forms(self):
        builder = ApplicationFormDataSourceHelper(
            self.domain,
            self.app,
            DATA_SOURCE_TYPE_FORM,
            self.form.unique_id
        )
        self.assertEqual('XFormInstance', builder.source_doc_type)
        expected_filter = {
            "type": "and",
            "filters": [
                {
                    "type": "boolean_expression",
                    "operator": "eq",
                    "expression": {
                        "type": "property_name",
                        "property_name": "xmlns"
                    },
                    "property_value": self.form.xmlns,
                },
                {
                    "type": "boolean_expression",
                    "operator": "eq",
                    "expression": {
                        "type": "property_name",
                        "property_name": "app_id"
                    },
                    "property_value": self.app.get_id,
                }
            ]
        }
        self.assertEqual(expected_filter, builder.filter)
        expected_property_names = [
            'username', 'userID', 'timeStart', 'timeEnd', 'deviceID',
            '/data/first_name', '/data/last_name', '/data/children', '/data/dob', '/data/state'
        ]
        self.assertEqual(expected_property_names, list(builder.data_source_properties.keys()))
        user_id_prop = builder.data_source_properties['userID']
        self.assertEqual('userID', user_id_prop.get_id())
        self.assertEqual('User ID', user_id_prop.get_text())
        name_prop = builder.data_source_properties['/data/first_name']
        self.assertEqual('/data/first_name', name_prop.get_id())
        self.assertEqual('First Name', name_prop.get_text())

    def test_builder_for_cases(self):
        builder = ApplicationCaseDataSourceHelper(self.domain, self.app, DATA_SOURCE_TYPE_CASE, self.case_type)
        self.assertEqual('CommCareCase', builder.source_doc_type)
        expected_filter = {
            "operator": "eq",
            "expression": {
                "type": "property_name",
                "property_name": "type"
            },
            "type": "boolean_expression",
            "property_value": self.case_type,
        }
        self.assertEqual(expected_filter, builder.filter)
        expected_property_names = [
            "closed", "closed_on", "first_name", "last_name", "modified_on", "name", "opened_on",
            "owner_id", "user_id", "computed/owner_name", "computed/user_name",
        ]
        self.assertEqual(expected_property_names, list(builder.data_source_properties.keys()))
        owner_name_prop = builder.data_source_properties['computed/owner_name']
        self.assertEqual('computed/owner_name', owner_name_prop.get_id())
        self.assertEqual('Case Owner', owner_name_prop.get_text())
        first_name_prop = builder.data_source_properties['first_name']
        self.assertEqual('first_name', first_name_prop.get_id())
        self.assertEqual('first name', first_name_prop.get_text())

    @flag_enabled('SHOW_OWNER_LOCATION_PROPERTY_IN_REPORT_BUILDER_TOGGLE')
    def test_owner_as_location(self, *args):
        builder = ApplicationCaseDataSourceHelper(self.domain, self.app, DATA_SOURCE_TYPE_CASE, self.case_type)

        self.assertTrue(COMPUTED_OWNER_LOCATION_PROPERTY_ID in builder.data_source_properties)
        self.assertTrue(COMPUTED_OWNER_LOCATION_WITH_DESENDANTS_PROPERTY_ID in builder.data_source_properties)
        self.assertTrue(
            COMPUTED_OWNER_LOCATION_ARCHIVED_WITH_DESCENDANTS_PROPERTY_ID in builder.data_source_properties
        )

        owner_location_prop = builder.data_source_properties[COMPUTED_OWNER_LOCATION_PROPERTY_ID]
        self.assertEqual(COMPUTED_OWNER_LOCATION_PROPERTY_ID, owner_location_prop.get_id())
        self.assertEqual('Case Owner (Location)', owner_location_prop.get_text())

        owner_location_prop_w_descendants = \
            builder.data_source_properties[COMPUTED_OWNER_LOCATION_WITH_DESENDANTS_PROPERTY_ID]
        self.assertEqual(COMPUTED_OWNER_LOCATION_WITH_DESENDANTS_PROPERTY_ID,
                         owner_location_prop_w_descendants.get_id())
        self.assertEqual('Case Owner (Location w/ Descendants)', owner_location_prop_w_descendants.get_text())

        owner_location_prop_archived_w_descendants = \
            builder.data_source_properties[COMPUTED_OWNER_LOCATION_ARCHIVED_WITH_DESCENDANTS_PROPERTY_ID]
        self.assertEqual(COMPUTED_OWNER_LOCATION_ARCHIVED_WITH_DESCENDANTS_PROPERTY_ID,
                         owner_location_prop_archived_w_descendants.get_id())
        self.assertEqual(
            'Case Owner (Location w/ Descendants and Archived Locations)',
            owner_location_prop_archived_w_descendants.get_text()
        )

    def test_builder_for_registry(self):
        case_type_for_registry = CaseType(domain=self.domain, name='registry_prop', fully_generated=True)
        case_type_for_registry.save()
        CaseProperty(case_type=case_type_for_registry, name='registry_property',
                     deprecated=False, data_type='plain', group=None).save()
        user = create_user("admin", "123")
        registry = create_registry_for_test(user, self.domain, invitations=[
            Invitation('foo', accepted=True), Invitation('user-reports', accepted=True),
        ], name='registry')
        registry_data_source = get_sample_registry_data_source(registry_slug=registry.slug)
        registry_data_source.save()
        registry.schema = RegistrySchemaBuilder(["registry_prop"]).build()
        registry.save()

        builder = RegistryCaseDataSourceHelper(self.domain, registry.slug, 'case', case_type_for_registry.name)

        expected_property_names = ['closed', 'closed_on', 'registry_property', 'computed/owner_name',
                                   'computed/user_name', 'commcare_project']
        self.assertEqual(expected_property_names, list(builder.data_source_properties.keys()))
        registry_prop = builder.data_source_properties['registry_property']
        self.assertEqual('registry_property', registry_prop.get_id())
        self.assertEqual('registry property', registry_prop.get_text())


class DataSourceReferenceTest(ReportBuilderDBTest):

    def test_reference_for_forms(self):
        form_data_source = get_form_data_source(self.app, self.form)
        form_data_source.save()
        reference = UnmanagedDataSourceHelper(
            self.domain, self.app, DATA_SOURCE_TYPE_RAW, form_data_source._id,
        )
        # todo: we should filter out some of these columns
        expected_property_names = [
            "doc_id", "inserted_at", "completed_time", "started_time", "username", "userID", "@xmlns", "@name",
            "App Version", "deviceID", "location", "app_id", "build_id", "@version", "state", "last_sync_token",
            "partial_submission", "received_on", "edited_on", "submit_ip",
            "form.first_name", "form.last_name", "form.children", "form.dob", "form.state",
            "form.case.@date_modified", 'form.case.@user_id', 'form.case.@case_id', 'form.case.update.first_name',
            'form.case.update.last_name', "count", "hq_user",
        ]

        self.assertItemsEqual(expected_property_names, list(reference.data_source_properties))
        user_id_prop = reference.data_source_properties['userID']
        self.assertEqual('userID', user_id_prop.get_id())
        self.assertEqual('userID', user_id_prop.get_text())
        name_prop = reference.data_source_properties['form.first_name']
        self.assertEqual('form.first_name', name_prop.get_id())
        self.assertEqual('form.first_name', name_prop.get_text())

    def test_reference_for_cases(self):
        case_data_source = get_case_data_source(self.app, self.case_type)
        case_data_source.save()
        reference = UnmanagedDataSourceHelper(
            self.domain, self.app, DATA_SOURCE_TYPE_RAW, case_data_source._id,
        )
        # todo: we should filter out some of these columns
        expected_property_names = [
            "doc_id", "inserted_at", "name", "case_type", "closed", "closed_by_user_id", "closed_date",
            "external_id", "last_modified_by_user_id", "last_modified_date", "opened_by_user_id", "opened_date",
            "owner_id", "server_last_modified_date", "state",
            "first_name", "last_name", "count",
        ]
        self.assertEqual(expected_property_names, list(reference.data_source_properties.keys()))
        owner_id_prop = reference.data_source_properties['owner_id']
        self.assertEqual('owner_id', owner_id_prop.get_id())
        self.assertEqual('owner_id', owner_id_prop.get_text())
        first_name_prop = reference.data_source_properties['first_name']
        self.assertEqual('first_name', first_name_prop.get_id())
        self.assertEqual('first_name', first_name_prop.get_text())


class ReportBuilderTest(ReportBuilderDBTest):

    def test_data_source_exclusivity(self):
        """
        Report builder reports based on the same form/case_type should have
        different data sources (they were previously sharing them)
        """

        # Make report
        builder_form = ConfigureListReportForm(
            self.domain,
            "Report one",
            self.app._id,
            "form",
            self.form.unique_id,
            existing_report=None,
            data={
                'user_filters': '[]',
                'default_filters': '[]',
                'columns':
                    '[{"property": "/data/first_name", "display_text": "first name", "calculation": "Group By"}]',
            }
        )
        self.assertTrue(builder_form.is_valid())
        report_one = builder_form.create_report()

        # Make another report
        builder_form = ConfigureListReportForm(
            self.domain,
            "Report two",
            self.app._id,
            "form",
            self.form.unique_id,
            existing_report=None,
            data={
                'user_filters': '[]',
                'default_filters': '[]',
                'columns':
                    '[{"property": "/data/first_name", "display_text": "first name", "calculation": "Group By"}]',
            }
        )
        self.assertTrue(builder_form.is_valid())
        report_two = builder_form.create_report()

        self.assertNotEqual(report_one.config_id, report_two.config_id)

    def test_updating_report_data_source(self):
        """
        Test that changing the app or number column for a report results in an update to the data source next time
        the report is saved.
        """

        # Make report
        builder_form = ConfigureTableReportForm(
            self.domain,
            "Test Report",
            self.app._id,
            "case",
            "some_case_type",
            existing_report=None,
            data={
                'group_by': ['closed'],
                'chart': 'bar',
                'user_filters': '[]',
                'default_filters': '[]',
                'columns': '[{"property": "closed", "display_text": "closed", "calculation": "Count per Choice"}]',
            }
        )
        self.assertTrue(builder_form.is_valid())
        report = builder_form.create_report()

        self.assertEqual(report.config.configured_indicators[0]['datatype'], "string")

        # Make an edit to the first report builder report
        builder_form = ConfigureTableReportForm(
            self.domain,
            "Test Report",
            self.app._id,
            "case",
            "some_case_type",
            existing_report=report,
            data={
                'group_by': ['user_id'],
                'chart': 'bar',
                'user_filters': '[]',
                'default_filters': '[]',
                # Note that a "Sum" calculation on the closed case property isn't very sensical, but doing it so
                # that I can have a numeric calculation without having to create real case properties for this case
                #  type.
                'columns': '[{"property": "closed", "display_text": "closed", "calculation": "Sum"}]',
            }
        )
        self.assertTrue(builder_form.is_valid())
        builder_form.update_report()

        # reload report data source, because report.config is memoized
        data_source = DataSourceConfiguration.get(report.config._id)
        # The closed property indicator should now be decimal type because the user indicated that it was numeric
        # by giving the column the "Sum" aggregation.
        self.assertEqual(data_source.configured_indicators[0]['datatype'], "decimal")

    def test_updating_report_that_shares_data_source(self):
        """
        If a report builder builder report shares a data source with another report,
        then editing the report builder report should result in a new data source
        being created for the report.
        """

        # Make report
        builder_form = ConfigureListReportForm(
            self.domain,
            "Test Report",
            self.app._id,
            "form",
            self.form.unique_id,
            existing_report=None,
            data={
                'user_filters': '[]',
                'default_filters': '[]',
                'columns':
                    '[{"property": "/data/first_name", "display_text": "first name", "calculation":"Group By"}]',
            }
        )
        self.assertTrue(builder_form.is_valid())
        report = builder_form.create_report()

        # Make another report that references the same data source
        report_two = ReportConfiguration(
            domain="domain",
            config_id=report.config_id
        )
        report_two.save()

        # Make an edit to the first report builder report
        builder_form = ConfigureListReportForm(
            self.domain,
            "Test Report",
            self.app._id,
            "form",
            self.form.unique_id,
            existing_report=report,
            data={
                'user_filters': '[]',
                'default_filters': '[]',
                'columns':
                    '[{"property": "/data/first_name", "display_text": "first name", "calculation": "Group By"}]',
            }
        )
        self.assertTrue(builder_form.is_valid())
        report = builder_form.update_report()

        self.assertNotEqual(report.config_id, report_two.config_id)

    def test_data_source_columns(self):
        """
        Report Builder should create a data source that includes columns for all possible aggregations, so that if
        the user switches between a list report and a summary report the data source has all the required columns

        (FB 268655)
        """
        builder_form = ConfigureListReportForm(
            self.domain,
            "My Report",
            self.app._id,
            "form",
            self.form.unique_id,
            data={
                'user_filters': '[]',
                'default_filters': '[]',
                'columns': """[
                    {"property": "/data/first_name", "display_text": "first name"},
                    {"property": "/data/last_name", "display_text": "last name"},
                    {"property": "/data/children", "display_text": "children"}
                ]""",
            }
        )
        self.assertTrue(builder_form.is_valid())
        with patch('corehq.apps.userreports.tasks.delete_data_source_task'):
            data_source_config_id = builder_form.create_temp_data_source_if_necessary('admin@example.com')
        data_source = DataSourceConfiguration.get(data_source_config_id)
        indicators = sorted([(ind['column_id'], ind['type']) for ind in data_source.configured_indicators])
        expected_indicators = [
            ('count', 'boolean'),
            ('data_children_25bd0e0d', 'expression'),           # "children" should have 2 columns because it is
            ('data_children_25bd0e0d_decimal', 'expression'),   # numeric
            ('data_dob_b6293169', 'expression'),
            ('data_first_name_ac8c51a7', 'expression'),
            ('data_last_name_ce36e9e1', 'expression'),
            ('data_state_6e36b993', 'choice_list'),
            ('data_state_6e36b993', 'expression'),
            ('deviceID_a7307e7d', 'expression'),
            ('timeEnd_09f40526', 'expression'),
            ('timeStart_c5a1ba73', 'expression'),
            ('userID_41e1d44e', 'expression'),
            ('username_ea02198f', 'expression'),
        ]
        self.assertEqual(indicators, expected_indicators)


class MultiselectQuestionTest(ReportBuilderDBTest):
    """
    Test class for report builder interactions with MultiSelect questions.
    """

    def testReportColumnOptions(self):
        """
        Confirm that form.report_column_options contains MultiselectQuestionColumnOption objects for mselect
        questions.
        """

        builder_form = ConfigureListReportForm(
            self.domain,
            "My Report",
            self.app._id,
            "form",
            self.form.unique_id,
        )
        self.assertEqual(
            type(builder_form.report_column_options["/data/state"]),
            MultiselectQuestionColumnOption
        )

    def testDataSource(self):
        """
        Confirm that data sources for reports with multiselects use "choice_list" indicators for mselect questions.
        """
        builder_form = ConfigureListReportForm(
            self.domain,
            "My Report",
            self.app._id,
            "form",
            self.form.unique_id,
            data={
                'user_filters': '[]',
                'default_filters': '[]',
                'columns':
                    '['
                    '   {"property": "/data/first_name", "display_text": "first name", "calculation": "Group By"},'
                    '   {"property": "/data/state", "display_text": "state", "calculation": "Count per Choice"}'
                    ']',
            }
        )
        self.assertTrue(builder_form.is_valid())
        report = builder_form.create_report()
        data_source = report.config
        mselect_indicators = [i for i in data_source.configured_indicators if i["type"] == "choice_list"]
        self.assertEqual(len(mselect_indicators), 1)
        mselect_indicator = mselect_indicators[0]
        self.assertEqual(set(mselect_indicator['choices']), {'MA', 'MN', 'VT'})

    def test_multiselect_aggregation(self):
        """
        Check report column aggregation for multi-select questions set to "group by"
        """
        builder_form = ConfigureTableReportForm(
            self.domain,
            "My Report",
            self.app._id,
            "form",
            self.form.unique_id,
            data={
                'user_filters': '[]',
                'default_filters': '[]',
                'columns': '[{"property": "/data/state", "display_text": "state", "calculation": "Group By"}]',
                'chart': 'pie',
            }
        )
        self.assertTrue(builder_form.is_valid())
        report = builder_form.create_report()
        self.assertEqual(report.columns[0]['aggregation'], 'simple')
