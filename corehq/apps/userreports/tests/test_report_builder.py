from __future__ import absolute_import
from __future__ import unicode_literals
import os
import six
from django.test import TestCase, SimpleTestCase
from mock import patch

from corehq.apps.app_manager.models import Application, Module
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.userreports.dbaccessors import delete_all_report_configs
from corehq.apps.userreports.models import DataSourceConfiguration, ReportConfiguration
from corehq.apps.userreports.reports.builder.columns import CountColumn, MultiselectQuestionColumnOption
from corehq.apps.userreports.reports.builder.forms import (
    ConfigureListReportForm,
    ConfigureTableReportForm,
)


def read(rel_path):
    path = os.path.join(os.path.dirname(__file__), *rel_path)
    with open(path) as f:
        return f.read()


factory = AppFactory()
module1, form1 = factory.new_basic_module('my_slug', 'my_case_type')
form1.source = read(['data', 'forms', 'simple.xml'])


class ReportBuilderDBTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(ReportBuilderDBTest, cls).setUpClass()
        cls.app = Application.new_app('domain', 'Untitled Application')
        module = cls.app.add_module(Module.new_module('Untitled Module', None))
        cls.form = cls.app.new_form(module.id, "Untitled Form", 'en', read(['data', 'forms', 'simple.xml']))
        cls.app.save()

    @classmethod
    def tearDownClass(cls):
        cls.app.delete()
        for config in DataSourceConfiguration.all():
            config.delete()
        delete_all_report_configs()
        super(ReportBuilderDBTest, cls).tearDownClass()


class ReportBuilderTest(ReportBuilderDBTest):

    def test_data_source_exclusivity(self):
        """
        Report builder reports based on the same form/case_type should have
        different data sources (they were previously sharing them)
        """

        # Make report
        builder_form = ConfigureListReportForm(
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
                    '   {"property": "/data/state", "display_text": "state", "calculation": "Count Per Choice"}'
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
