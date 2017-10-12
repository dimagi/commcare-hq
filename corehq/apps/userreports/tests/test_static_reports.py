from __future__ import absolute_import
import os

import mock
from django.test import SimpleTestCase
from django.test.utils import override_settings
from corehq.util.test_utils import TestFileMixin
from corehq.apps.userreports.models import StaticReportConfiguration, id_is_static


class TestStaticReportConfig(SimpleTestCase, TestFileMixin):

    file_path = ('data', 'static_reports')
    root = os.path.dirname(__file__)

    def test_wrap(self):
        wrapped = StaticReportConfiguration.wrap(self.get_json('static_report_config'))
        self.assertEqual(["example", "dimagi"], wrapped.domains)

    def test_get_all(self):
        with override_settings(STATIC_UCR_REPORTS=[self.get_path('static_report_config', 'json')]):
            all = list(StaticReportConfiguration.all())
            self.assertEqual(2, len(all))
            example, dimagi = all
            self.assertEqual('example', example.domain)
            self.assertEqual('dimagi', dimagi.domain)
            for config in all:
                self.assertEqual('Custom Title', config.title)

    def test_production_config(self):
        _call_center_domain_mock = mock.patch(
            'corehq.apps.callcenter.data_source.call_center_data_source_configuration_provider'
        )
        _call_center_domain_mock.start()
        messages = []
        for report_config in StaticReportConfiguration.all(ignore_server_environment=True):
            report_config.validate()
            if not id_is_static(report_config.config_id):
                continue

            columns_id = []

            for column in report_config.columns:
                if column['type'] == 'field':
                    columns_id.append(column['field'])
                elif column['type'] == 'percent':
                    columns_id.extend([column['numerator']['field'], column['denominator']['field']])

            data_source_config = report_config.config

            data_source_columns_id = [
                column['column_id']
                for column in data_source_config.configured_indicators
            ] + ['doc_id', 'inserted_at']

            missing_columns = set(columns_id) - set(data_source_columns_id)
            if missing_columns:
                messages.append(
                    'Columns from {} not found in the data source: {}'.format(
                        report_config.title, ', '.join(missing_columns)
                    )
                )
        if messages:
            self.fail('\n' + '\n'.join(set(messages)))
        _call_center_domain_mock.stop()
