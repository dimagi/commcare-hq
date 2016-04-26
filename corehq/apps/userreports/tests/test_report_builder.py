import os
from django.test import TestCase
from corehq.apps.app_manager.const import APP_V2
from corehq.apps.app_manager.models import Application, Module
from corehq.apps.userreports.dbaccessors import delete_all_report_configs
from corehq.apps.userreports.models import DataSourceConfiguration
from corehq.apps.userreports.reports.builder.forms import ConfigureListReportForm


def read(rel_path):
    path = os.path.join(os.path.dirname(__file__), *rel_path)
    with open(path) as f:
        return f.read()


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
