from django.test.testcases import SimpleTestCase
from mock import patch

from corehq.apps.callcenter.data_source import call_center_data_source_provider
from corehq.apps.callcenter.utils import DomainLite


class TestCallCenterDataSources(SimpleTestCase):

    @patch('corehq.apps.callcenter.data_source.get_call_center_domains')
    def test_call_center_data_source_provider(self, get_call_center_domains):
        get_call_center_domains.return_value = [
            DomainLite('domain1', None, None, True),
            DomainLite('domain2', None, None, True),
            DomainLite('domain3', None, None, False)
        ]

        data_sources = list(call_center_data_source_provider())
        self.assertEqual(6, len(data_sources))

        domains = [ds.domain for ds in data_sources]
        self.assertEqual(
            (['domain1'] * 3) + (['domain2'] * 3),
            domains
        )

        table_ids = [ds.table_id for ds in data_sources]
        self.assertEqual(
            ['cc_forms', 'cc_cases', 'cc_case_actions'] * 2,
            table_ids
        )
