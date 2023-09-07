from django.test import SimpleTestCase

from corehq.apps.export.export import _get_base_query, get_export_query
from corehq.apps.export.filters import TermFilter
from corehq.apps.export.models import FormExportInstance

"""
This file exists to test code in corehq/apps/export/export.py
"""


class GetExportQueryTests(SimpleTestCase):

    def test_returns_base_query_if_no_filters(self):
        instance = FormExportInstance(domain='export_test')
        base_query = _get_base_query(instance)

        export_query = get_export_query(instance, [])

        self.assertEqual(export_query.raw_query, base_query.raw_query)
        self.assertEqual(export_query.filters, base_query.filters)

    def test_export_filter_instance_returns_successfully(self):
        instance = FormExportInstance(domain='export_test')
        base_query = _get_base_query(instance)
        export_filter = TermFilter(term='_id', value='test')

        export_query = get_export_query(instance, [export_filter])

        self.assertTrue({'term': {'_id': 'test'}} not in base_query.filters)
        self.assertTrue({'term': {'_id': 'test'}} in export_query.filters)

    def test_elasticsearch_filter_returns_successfully(self):
        instance = FormExportInstance(domain='export_test')
        base_query = _get_base_query(instance)
        es_filter = {'term': {'_id': 'test'}}

        export_query = get_export_query(instance, [es_filter])

        self.assertTrue({'term': {'_id': 'test'}} not in base_query.filters)
        self.assertTrue({'term': {'_id': 'test'}} in export_query.filters)
