from __future__ import absolute_import
from __future__ import unicode_literals
import os
from collections import Counter, defaultdict
from mock import patch, MagicMock

from django.test import SimpleTestCase
from django.test.utils import override_settings
from corehq.util.test_utils import TestFileMixin
from corehq.apps.userreports.tests.utils import domain_lite
from corehq.apps.userreports.models import StaticReportConfiguration, StaticDataSourceConfiguration
from six.moves import filter


class TestStaticReportConfig(SimpleTestCase, TestFileMixin):

    file_path = ('data', 'static_reports')
    root = os.path.dirname(__file__)

    @classmethod
    def setUpClass(cls):
        super(TestStaticReportConfig, cls).setUpClass()
        cls.configs = list(StaticDataSourceConfiguration.all())

    def setUp(self):
        super(TestStaticReportConfig, self).setUp()
        StaticReportConfiguration.by_id_mapping.reset_cache(StaticReportConfiguration.__class__)

    def test_wrap(self):
        wrapped = StaticReportConfiguration.wrap(self.get_json('static_report_config'))
        self.assertEqual(["example", "dimagi"], wrapped.domains)

    def test_get_all_json(self):
        with override_settings(STATIC_UCR_REPORTS=[self.get_path('static_report_config', 'json')]):
            self.assertEqual(2, len(self.configs))
            example, dimagi = self.configs
            self.assertEqual('example', example.domain)
            self.assertEqual('dimagi', dimagi.domain)
            for config in self.configs:
                self.assertEqual('Custom Title', config.title)

    def test_get_all_yaml(self):
        with override_settings(STATIC_UCR_REPORTS=[self.get_path('static_report_config', 'yaml')]):
            self.assertEqual(2, len(self.configs))
            example, dimagi = self.configs
            self.assertEqual('example', example.domain)
            self.assertEqual('dimagi', dimagi.domain)
            for config in self.configs:
                self.assertEqual('Custom Title', config.title)

    def test_production_config(self):
        for report_config in self.configs:
            report_config.validate()

    def test_for_report_id_conflicts(self):
        counts = Counter(rc.get_id for rc in self.configs)
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

        configs_missing_data_source = list(filter(has_no_data_source, self.configs))

        msg = ("There are {} report configs which reference data sources that "
               "don't exist (or which don't exist on that domain):\n{}".format(
                   len(configs_missing_data_source),
                   "\n".join(config.get_id for config in configs_missing_data_source)))
        self.assertEqual(0, len(configs_missing_data_source), msg)
