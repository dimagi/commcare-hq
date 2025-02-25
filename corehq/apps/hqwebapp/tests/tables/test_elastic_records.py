from django.test import TestCase, RequestFactory
from django_tables2.utils import OrderBy

from corehq.apps.case_search.utils import get_case_id_sort_block
from corehq.apps.data_dictionary.models import CaseType
from corehq.apps.es.tests.utils import (
    case_search_es_setup,
    es_test,
)
from corehq.apps.es import CaseSearchES
from corehq.apps.es.case_search import case_search_adapter
from corehq.apps.hqwebapp.tables.elasticsearch.records import CaseSearchElasticRecord
from corehq.apps.hqwebapp.tests.tables.generator import get_case_blocks
from corehq.form_processor.tests.utils import FormProcessorTestUtils


@es_test(requires=[case_search_adapter], setup_class=True)
class CaseSearchElasticRecordTests(TestCase):
    domain = 'test-cs-table-data'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        case_search_es_setup(cls.domain, get_case_blocks())
        cls.case_type_obj = CaseType(domain=cls.domain, name='person')
        cls.case_type_obj.save()

        cls.request = RequestFactory().get('/cases/')
        cls.request.domain = None  # so that get_timezone doesn't do a complex lookup

    @classmethod
    def tearDownClass(cls):
        FormProcessorTestUtils.delete_all_cases()
        cls.case_type_obj.delete()
        super().tearDownClass()

    def test_sorting_by_name(self):
        query = CaseSearchES().domain(self.domain)
        accessors = [OrderBy('-name')]
        query = CaseSearchElasticRecord.get_sorted_query(query, accessors)
        expected = [{
            'name.exact': {'order': 'desc'},
        }]
        self.assertEqual(query.es_query['sort'], expected)

    def test_sorting_by_case_id(self):
        query = CaseSearchES().domain(self.domain)
        accessors = [OrderBy('@case_id')]
        query = CaseSearchElasticRecord.get_sorted_query(query, accessors)
        expected = get_case_id_sort_block(is_descending=False)
        self.assertEqual(query.es_query['sort'], expected)

    def test_sorting_by_case_property(self):
        query = CaseSearchES().domain(self.domain)
        aliases = [OrderBy('-description')]
        query = CaseSearchElasticRecord.get_sorted_query(query, aliases)
        expected = [
            {
                'case_properties.value.numeric': {
                    'order': 'desc',
                    'nested_path': 'case_properties',
                    'nested_filter': {
                        'term': {
                            'case_properties.key.exact': 'description'
                        }
                    },
                    'missing': None
                }
            },
            {
                'case_properties.value.date': {
                    'order': 'desc',
                    'nested_path': 'case_properties',
                    'nested_filter': {
                        'term': {
                            'case_properties.key.exact': 'description'
                        }
                    },
                    'missing': None
                }
            },
            {
                'case_properties.value.exact': {
                    'order': 'desc',
                    'nested_path': 'case_properties',
                    'nested_filter': {
                        'term': {
                            'case_properties.key.exact': 'description'
                        }
                    },
                    'missing': None
                }
            }
        ]
        self.assertEqual(query.es_query['sort'], expected)

    @staticmethod
    def _get_hit_from_query(query, index):
        return query.start(index).size(1).run().raw['hits']['hits'][0]

    def test_get_reserved_property(self):
        """
        A case has `domain` as an actual property or a case property, if supplied.
        This "case property" is always user-inputted and is unrelated to the domain
        the case belongs to. We want to make sure the "case property" is the value returned.
        """
        query = CaseSearchES().domain(self.domain)
        case_hit = self._get_hit_from_query(query, 2)
        record = CaseSearchElasticRecord(case_hit, self.request)
        self.assertEqual(record['domain'], 'user input')

    def test_get_non_existing_property(self):
        query = CaseSearchES().domain(self.domain)
        case_hit = self._get_hit_from_query(query, 4)
        record = CaseSearchElasticRecord(case_hit, self.request)
        self.assertEqual(record['does_not_exist'], None)

    def test_get_property(self):
        query = CaseSearchES().domain(self.domain)
        case_hit = self._get_hit_from_query(query, 0)
        record = CaseSearchElasticRecord(case_hit, self.request)
        self.assertEqual(record['color'], 'red')

    def test_get_name(self):
        query = CaseSearchES().domain(self.domain)
        case_hit = self._get_hit_from_query(query, 5)
        record = CaseSearchElasticRecord(case_hit, self.request)
        self.assertEqual(record['name'], 'Trish Hartmann')
