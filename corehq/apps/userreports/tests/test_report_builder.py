import os
from django.test import TestCase, SimpleTestCase
from mock import patch, MagicMock

from corehq.apps.app_manager.const import APP_V2
from corehq.apps.app_manager.models import Application, Module, Form
from corehq.apps.app_manager.tests import AppFactory
from corehq.apps.userreports.dbaccessors import delete_all_report_configs
from corehq.apps.userreports.models import DataSourceConfiguration
from corehq.apps.userreports.reports.builder.columns import CountColumn
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


@patch('corehq.apps.app_manager.models.Application.get', return_value=factory.app)
@patch('corehq.apps.app_manager.models.Form.get_form', return_value=form1)
class ConfigureReportFormsTest(SimpleTestCase):

    def test_count_column_existence(self, _, __):
        """
        Confirm that aggregated reports have a count column option, and that
        non aggregated reports do not.
        """

        def get_count_column_columns(configuration_form):
            return len(filter(
                lambda x: isinstance(x, CountColumn),
                configuration_form.report_column_options.values()
            ))

        list_report_form = ConfigureListReportForm(
            "my report",
            factory.app._id,
            "form",
            form1.unique_id,
        )
        self.assertEqual(get_count_column_columns(list_report_form), 0)

        table_report_form = ConfigureTableReportForm(
            "my report",
            factory.app._id,
            "form",
            form1.unique_id,
        )
        self.assertEqual(get_count_column_columns(table_report_form), 1)


class ReportBuilderTest(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = Application.new_app('domain', 'Untitled Application', application_version=APP_V2)
        module = cls.app.add_module(Module.new_module('Untitled Module', None))
        cls.form = cls.app.new_form(module.id, "Untitled Form", 'en', read(['data', 'forms', 'simple.xml']))
        cls.app.save()

    @classmethod
    def tearDownClass(cls):
        cls.app.delete()
        for config in DataSourceConfiguration.all():
            config.delete()
        delete_all_report_configs()

    def test_updating_out_of_date_report(self):
        """
        Test that editing a report for an outdated data source creates a new data source.
        Data sources are tied to app version.
        """

        # Make report
        builder_form = ConfigureListReportForm(
            "Test Report",
            self.app._id,
            "form",
            self.form.unique_id,
            existing_report=None,
            data={
                'filters': '[]',
                'columns': '[{"property": "/data/first_name", "display_text": "first name"}]',
            }
        )
        self.assertTrue(builder_form.is_valid())
        report = builder_form.create_report()
        first_data_source_id = report.config_id

        # Bump version of app by saving it
        self.app.save()

        # Modify the report
        builder_form = ConfigureListReportForm(
            "Test Report",
            self.app._id,
            "form",
            self.form.unique_id,
            existing_report=report,
            data={
                'filters': '[]',
                'columns': '[{"property": "/data/first_name", "display_text": "first name"}]',
            }
        )
        self.assertTrue(builder_form.is_valid())
        report = builder_form.update_report()
        second_data_source_id = report.config_id

        self.assertNotEqual(first_data_source_id, second_data_source_id)
