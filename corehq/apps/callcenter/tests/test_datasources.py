from __future__ import absolute_import
from __future__ import unicode_literals
import itertools
from django.test.testcases import SimpleTestCase
from mock import patch

from corehq.apps.callcenter.data_source import call_center_data_source_configuration_provider
from corehq.apps.callcenter.utils import DomainLite


class TestCallCenterDataSources(SimpleTestCase):

    @patch('corehq.apps.callcenter.data_source.get_call_center_domains')
    def test_call_center_data_source_provider(self, get_call_center_domains):
        get_call_center_domains.return_value = [
            DomainLite('domain1', None, None, True),
            DomainLite('domain2', None, None, True),
            DomainLite('domain3', None, None, False)
        ]

        data_source_configs = [config for config, _ in call_center_data_source_configuration_provider()]
        self.assertEqual(3, len(data_source_configs))

        domains = set(itertools.chain(*[config.domains for config in data_source_configs]))
        self.assertEqual(
            set((['domain1'] * 3) + (['domain2'] * 3)),
            domains
        )

        table_ids = [config.config['table_id'] for config in data_source_configs]
        self.assertEqual(
            ['cc_forms', 'cc_cases', 'cc_case_actions'],
            table_ids
        )
