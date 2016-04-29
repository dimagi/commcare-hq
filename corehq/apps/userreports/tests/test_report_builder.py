import os
from django.test import TestCase
from corehq.util.test_utils import TestFileMixin
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.userreports.dbaccessors import delete_all_report_configs
from corehq.apps.userreports.models import DataSourceConfiguration
from corehq.apps.userreports.sql.util import get_column_name
from corehq.apps.userreports.reports.builder.forms import (
    ConfigureListReportForm,
    ConfigureTableReportForm,
)


class ReportBuilderTest(TestCase, TestFileMixin):
    root = os.path.dirname(__file__)
    file_path = ('data', 'forms')

    case_type = 'primates'

    @classmethod
    def setUpClass(cls):
        cls.factory = AppFactory(domain='domain')
        m0 = cls.factory.new_basic_module('Primates', 'primates')
        f0 = cls.factory.new_form(m0[0])
        f0.source = cls.get_xml('simple')
        cls.factory.form_requires_case(
            f0,
            cls.case_type,
            update={
                'age': '/data/age',
                'weight': '/data/weight',
                'sex': '/data/sex',
            }
        )
        cls.form = f0
        cls.app = cls.factory.app
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

    def test_build_aggregation_report(self):
        # Make report
        builder_form = ConfigureTableReportForm(
            "Test Report",
            self.app._id,
            "case",
            self.case_type,
            existing_report=None,
            data={
                'filters': '[]',
                'group_by': 'sex',
                'columns': '[{"property": "age", "display_text": "Age", "calculation": "Average"}]',
            }
        )
        self.assertTrue(builder_form.is_valid())
        report = builder_form.create_report()
        self._assertInColumns(get_column_name('age_decimal'), report.columns)

    def test_build_aggregation_report_update(self):
        builder_form = ConfigureTableReportForm(
            "Test Report",
            self.app._id,
            "case",
            self.case_type,
            existing_report=None,
            data={
                'filters': '[]',
                'group_by': 'sex',
                'columns': '[{"property": "age", "display_text": "Age", "calculation": "Average"}]',
            }
        )
        self.assertTrue(builder_form.is_valid())
        builder_form.create_report()

        builder_form = ConfigureTableReportForm(
            "Test Report",
            self.app._id,
            "case",
            self.case_type,
            existing_report=None,
            data={
                'filters': '[]',
                'group_by': 'sex',
                'columns': '[{"property": "weight", "display_text": "Weight", "calculation": "Sum"}]',
            }
        )
        self.assertTrue(builder_form.is_valid())
        report = builder_form.create_report()
        self._assertInColumns(get_column_name('weight_decimal'), report.columns)
        self._assertNotInColumns(get_column_name('age_decimal'), report.columns)

    def test_build_aggregation_report_with_same_group_by(self):
        builder_form = ConfigureTableReportForm(
            "Test Report",
            self.app._id,
            "case",
            self.case_type,
            existing_report=None,
            data={
                'filters': '[]',
                'group_by': 'age',
                'columns': '[{"property": "age", "display_text": "Age", "calculation": "Average"}]',
            }
        )
        self.assertTrue(builder_form.is_valid())
        report = builder_form.create_report()
        self._assertInColumns(get_column_name('age_decimal'), report.columns)
        self._assertInColumns(get_column_name('age'), report.columns)

    def _assertInColumns(self, column_id, columns):
        self.assertIn(column_id, map(lambda c: c['field'], columns))

    def _assertNotInColumns(self, column_id, columns):
        self.assertNotIn(column_id, map(lambda c: c['field'], columns))
