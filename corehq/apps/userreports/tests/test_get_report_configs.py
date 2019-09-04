import os
import uuid

from django.test import SimpleTestCase
from django.test.utils import override_settings

from mock import MagicMock, patch

from corehq.apps.userreports.exceptions import ReportConfigurationNotFoundError
from corehq.apps.userreports.models import (
    ReportConfiguration,
    StaticReportConfiguration,
    get_report_configs,
)
from corehq.util.test_utils import TestFileMixin


@patch('corehq.apps.userreports.models.ReportConfiguration.get_db', new=MagicMock())
@patch('corehq.apps.userreports.models.get_docs', new=MagicMock(return_value=[]))
class TestGetReportConfigs(SimpleTestCase, TestFileMixin):

    file_path = ('data', 'static_reports')
    root = os.path.dirname(__file__)

    def setUp(self):
        super(TestGetReportConfigs, self).setUp()
        StaticReportConfiguration.by_id_mapping.reset_cache(StaticReportConfiguration.__class__)

    def test_static_reports(self):
        with override_settings(STATIC_UCR_REPORTS=[
            self.get_path('static_report_config', 'json'),
            self.get_path('static_report_2_config', 'json')
        ]):
            reports = get_report_configs(
                [StaticReportConfiguration.get_doc_id('example', 'a-custom-report', False)],
                'example'
            )
            self.assertEqual(len(reports), 1)

            reports = get_report_configs(
                [
                    StaticReportConfiguration.get_doc_id('example', 'a-custom-report', False),
                    StaticReportConfiguration.get_doc_id('example', 'another-custom-report', False),
                ],
                'example'
            )
            self.assertEqual(len(reports), 2)

    def test_non_existent_id(self):
        with override_settings(STATIC_UCR_REPORTS=[self.get_path('static_report_config', 'json')]):
            with self.assertRaises(ReportConfigurationNotFoundError):
                get_report_configs(['non-existent-id'], 'example')

    def test_wrong_domain(self):
        with override_settings(STATIC_UCR_REPORTS=[self.get_path('static_report_config', 'json')]):
            with self.assertRaises(ReportConfigurationNotFoundError):
                get_report_configs(['a-custom-report'], 'wrong-domain')

    def test_mixed_reports(self):
        dynamic_report_id = uuid.uuid4().hex
        dynamic_report = ReportConfiguration(
            _id=dynamic_report_id,
            domain='example',
            config_id=uuid.uuid4().hex

        )

        def get_docs_mock(db, ids):
            if ids == [dynamic_report_id]:
                return [dynamic_report.to_json()]
            return []

        with patch('corehq.apps.userreports.models.get_docs', new=get_docs_mock):
            with override_settings(STATIC_UCR_REPORTS=[self.get_path('static_report_config', 'json')]):
                configs = get_report_configs(
                    [dynamic_report_id, StaticReportConfiguration.get_doc_id('example', 'a-custom-report', False)],
                    'example'
                )
                self.assertEqual(len(configs), 2)
