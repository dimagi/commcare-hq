from django.test import TestCase, override_settings

from corehq.apps.userreports.models import StaticDataSourceConfiguration
from corehq.util.test_utils import generate_cases
from custom.icds_reports.const import DASHBOARD_DOMAIN
from custom.icds_reports.models.util import UCR_MAPPING


@override_settings(STATIC_DATA_SOURCE_PROVIDERS=[])
class TestReconMapping(TestCase):
    pass


_test_cases = [
    (doc_type, data_source_id)
    for doc_type, data_sources in UCR_MAPPING.items()
    for data_source_id in data_sources
]


@generate_cases(_test_cases, TestReconMapping)
def test_doc_filter_mapping(self, doc_type, data_source_id):
    config_id = StaticDataSourceConfiguration.get_doc_id(DASHBOARD_DOMAIN, data_source_id)
    config = StaticDataSourceConfiguration.by_id(config_id)

    doc_filters = UCR_MAPPING[doc_type][data_source_id]
    self.assertEqual(doc_type, config.referenced_doc_type)
    self.assertEqual(set(doc_filters), set(config.get_case_type_or_xmlns_filter()))
