import os
from collections import Counter, defaultdict

from django.test import SimpleTestCase
from django.test.utils import override_settings

from unittest.mock import MagicMock, patch

from corehq.apps.userreports.models import (
    StaticDataSourceConfiguration,
    StaticReportConfiguration,
)
from corehq.apps.userreports.tests.utils import domain_lite
from corehq.util.test_utils import TestFileMixin


class TestStaticReportConfig(SimpleTestCase, TestFileMixin):

    file_path = ('data', 'static_reports')
    root = os.path.dirname(__file__)

    def setUp(self):
        super(TestStaticReportConfig, self).setUp()
        StaticReportConfiguration.by_id_mapping.reset_cache(StaticReportConfiguration.__class__)

    def test_wrap(self):
        wrapped = StaticReportConfiguration.wrap(self.get_json('static_report_config'))
        self.assertEqual(["example", "dimagi"], wrapped.domains)

    def test_get_all_json(self):
        path = self.get_path('static_report_config', 'json')
        with patch("corehq.apps.userreports.models.static_ucr_report_paths", return_value=[path]), \
             override_settings(STATIC_UCR_REPORTS=[path]):
            all = list(StaticReportConfiguration.all())
            self.assertEqual(4, len(all))
            example, dimagi, example1, dimagi1 = all
            self.assertEqual('example', example.domain)
            self.assertEqual('example', example1.domain)
            self.assertEqual('dimagi', dimagi.domain)
            self.assertEqual('dimagi', dimagi1.domain)
            for config in all:
                self.assertEqual('Custom Title', config.title)

    def test_get_all_yaml(self):
        with patch("corehq.apps.userreports.models.static_ucr_report_paths", return_value=[]), \
             override_settings(STATIC_UCR_REPORTS=[self.get_path('static_report_config', 'yaml')]):
            all = list(StaticReportConfiguration.all())
            self.assertEqual(2, len(all))
            example, dimagi = all
            self.assertEqual('example', example.domain)
            self.assertEqual('dimagi', dimagi.domain)
            for config in all:
                self.assertEqual('Custom Title', config.title)

    @patch('corehq.apps.callcenter.data_source.get_call_center_domains')
    def test_production_config(self, mock_get_call_center_domains):
        mock_get_call_center_domains.return_value = []
        for report_config in StaticReportConfiguration.all():
            report_config.validate()

    def test_for_report_id_conflicts(self):
        counts = Counter(rc.get_id for rc in
                         StaticReportConfiguration.all())
        duplicates = [k for k, v in counts.items() if v > 1]
        msg = "The following report configs have duplicate generated report_ids:\n{}".format(
            "\n".join("report_id: {}".format(report_id) for report_id in duplicates)
        )
        self.assertEqual(0, len(duplicates), msg)

    @patch('corehq.apps.callcenter.data_source.get_call_center_domains',
           MagicMock(return_value=[domain_lite('cc1')]))
    def test_data_sources_actually_exist(self):

        data_sources_on_domain = defaultdict(set)
        for data_source in StaticDataSourceConfiguration.all():
            data_sources_on_domain[data_source.domain].add(data_source.get_id)

        def has_no_data_source(report_config):
            available_data_sources = data_sources_on_domain[report_config.domain]
            return report_config.config_id not in available_data_sources

        all_configs = StaticReportConfiguration.all()
        configs_missing_data_source = list(filter(has_no_data_source, all_configs))

        msg = ("There are {} report configs which reference data sources that "
               "don't exist (or which don't exist on that domain):\n{}".format(
                   len(configs_missing_data_source),
                   "\n".join(config.get_id for config in configs_missing_data_source)))
        self.assertEqual(0, len(configs_missing_data_source), msg)
