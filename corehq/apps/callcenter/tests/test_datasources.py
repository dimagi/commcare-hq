from __future__ import absolute_import
from __future__ import unicode_literals

from django.test.testcases import SimpleTestCase
from mock import patch

from corehq.apps.callcenter.data_source import call_center_data_source_configuration_provider
from corehq.apps.callcenter.utils import DomainLite
from corehq.util.test_utils import generate_cases


class TestCallCenterDataSources(SimpleTestCase):
    pass


@generate_cases([
    (DomainLite('d', None, None, True, True, False, False), ['cc_forms']),
    (DomainLite('d', None, None, True, False, True, False), ['cc_cases']),
    (DomainLite('d', None, None, True, False, False, True), ['cc_case_actions']),
    (DomainLite('d', None, None, True, True, True, True), ['cc_forms', 'cc_cases', 'cc_case_actions']),
], TestCallCenterDataSources)
def test_call_center_data_source_provider(self, domain, tables):
    with patch('corehq.apps.callcenter.data_source.get_call_center_domains') as get_call_center_domains:
        get_call_center_domains.return_value = [domain]
        configs = [config for config, _ in call_center_data_source_configuration_provider()]
    table_ids = [config.config['table_id'] for config in configs]
    self.assertEqual(tables, table_ids)
