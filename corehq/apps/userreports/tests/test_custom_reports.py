import os
from django.test import SimpleTestCase
from django.test.utils import override_settings
from corehq.apps.app_manager.tests import TestFileMixin
from corehq.apps.userreports.models import CustomDataSourceConfiguration, CustomReportConfiguration


class TestCustomReportConfig(SimpleTestCase, TestFileMixin):

    file_path = ('data', 'custom_reports')
    root = os.path.dirname(__file__)

    def test_wrap(self):
        wrapped = CustomReportConfiguration.wrap(self.get_json('custom_report_config'))
        self.assertEqual(["example", "dimagi"], wrapped.domains)

    def test_get_all(self):
        with override_settings(CUSTOM_UCR_REPORTS=[self.get_path('custom_report_config', 'json')]):
            all = list(CustomReportConfiguration.all())
            self.assertEqual(2, len(all))
            example, dimagi = all
            self.assertEqual('example', example.domain)
            self.assertEqual('dimagi', dimagi.domain)
            for config in all:
                self.assertEqual('Custom Title', config.title)

    def test_production_config(self):
        for data_source in CustomDataSourceConfiguration.all():
            data_source.validate()
