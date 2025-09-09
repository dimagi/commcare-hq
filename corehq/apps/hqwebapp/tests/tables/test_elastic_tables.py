from django.test import TestCase, RequestFactory
from django_tables2 import columns
from django_tables2.utils import OrderByTuple

from corehq.apps.data_dictionary.models import CaseType
from corehq.apps.es.tests.utils import (
    case_search_es_setup,
    es_test,
)
from corehq.apps.es import CaseSearchES
from corehq.apps.es.case_search import case_search_adapter
from corehq.apps.hqwebapp.tables.elasticsearch.records import CaseSearchElasticRecord
from corehq.apps.hqwebapp.tables.elasticsearch.tables import ElasticTable
from corehq.apps.hqwebapp.tests.tables.generator import get_case_blocks
from corehq.form_processor.tests.utils import FormProcessorTestUtils


@es_test(requires=[case_search_adapter], setup_class=True)
class ElasticTableTests(TestCase):
    domain = 'test-cs-table-data'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        case_search_es_setup(cls.domain, get_case_blocks())
        cls.case_type_obj = CaseType(domain=cls.domain, name='person')
        cls.case_type_obj.save()

        cls.request = RequestFactory().get('/cases/')
        cls.request.domain = None  # so that get_timezone doesn't do a complex lookup

        class TestCaseSearchElasticTable(ElasticTable):
            record_class = CaseSearchElasticRecord

            name = columns.Column(
                verbose_name="Case Name",
            )
            case_type = columns.Column(
                accessor="@case_type",
                verbose_name="Case Type",
            )
            status = columns.Column(
                accessor="@status",
                verbose_name="Status",
            )
            opened_on = columns.Column(
                verbose_name="Opened On",
            )

        cls.table_class = TestCaseSearchElasticTable

    @classmethod
    def tearDownClass(cls):
        FormProcessorTestUtils.delete_all_cases()
        cls.case_type_obj.delete()
        super().tearDownClass()

    def test_order_by_alias_to_accessor(self):
        """
        We want to make sure that the alias for `status` is converted to
        its accessor `@status` to generate the correct sorting block in the
        CaseSearchES query when `order_by` is called on the `ElasticTableData` instance.
        """
        query = CaseSearchES().domain(self.domain)
        table = self.table_class(data=query, request=self.request)
        aliases = OrderByTuple(['-status'])
        table.data.order_by(aliases)
        expected = [{'closed': {'order': 'desc'}}]
        self.assertEqual(table.data.query.es_query['sort'], expected)
        record = table.data[0]
        self.assertEqual(record['@status'], 'closed')
        self.assertEqual(record['name'], "Olivia Joeri")

    def test_slicing_and_data(self):
        """
        We want to ensure that slicing ElasticTableData returns a list of
        instances of that table's `record_class`.
        """
        query = CaseSearchES().domain(self.domain)
        table = self.table_class(data=query, request=self.request)
        results = table.data[5:10]
        self.assertEqual(len(results), 5)
        self.assertEqual(type(results), list)
        self.assertEqual(type(results[0]), self.table_class.record_class)

    def test_get_single_record_returns_object(self):
        """
        We want to ensure that getting a single "key" from ElasticTableData
        (as opposed to a "slice") returns a single instance that matches
        of the related table's `record_class`.
        """
        query = CaseSearchES().domain(self.domain)
        table = self.table_class(data=query, request=self.request)
        record = table.data[0]
        self.assertEqual(type(record), self.table_class.record_class)

    def test_get_out_of_bounds_record_raises_index_error(self):
        """
        We want to ensure that getting a "key" from ElasticTableData that
        is out-of-bounds raises an `IndexError`
        """
        query = CaseSearchES().domain(self.domain)
        table = self.table_class(data=query, request=self.request)
        with self.assertRaises(IndexError):
            table.data[50]

    def test_data_length(self):
        """
        We want to ensure that getting calling `len` of `ElasticTableData`
        returns the expected total number of records in the query.
        """
        query = CaseSearchES().domain(self.domain)
        table = self.table_class(data=query, request=self.request)
        self.assertEqual(len(table.data), 11)
