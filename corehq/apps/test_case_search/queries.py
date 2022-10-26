from copy import deepcopy
from pprint import pprint

from corehq.apps.es import CaseSearchES as OldCaseSearchES
from corehq.apps.es.case_search import (
    case_property_text_query,
    exact_case_property_text_query,
    sounds_like_text_query,
)
from corehq.apps.es.es_query import ESQuerySet
from corehq.elastic import get_es_new
from corehq.pillows.mappings.case_mapping import CASE_ES_TYPE

from .const import PATIENT_CASE_TYPE, TEST_INDEX_NAME, TEST_DOMAIN_NAME


class NewCaseSearchES(OldCaseSearchES):

    def run(self):
        # We need to override `run` since this index isn't in the registry
        es = get_es_new()
        results = es.search(
            index=TEST_INDEX_NAME,
            doc_type=CASE_ES_TYPE,
            body=self.raw_query,
        )
        for result in results['hits']['hits']:
            result['_source']['_id'] = result['_id']
        return ESQuerySet(results, deepcopy(self))

    def matching_patients(self, limit=10):
        headers = ["case_id", "first name", "last name"]
        row_format = "{:>38}" * len(headers)
        print(row_format.format(*headers))
        query = self.size(limit).case_type(PATIENT_CASE_TYPE).domain(TEST_DOMAIN_NAME)
        for doc in query.run().hits:
            case_properties = {
                prop['key']: prop['value']
                for prop in doc['case_properties']
            }
            print(row_format.format(
                doc['_id'], case_properties['first_name'], case_properties['last_name']
            ))


def run_all_queries():
    print("Query Results:")

    print("\nUnfiltered query (all results)")
    NewCaseSearchES().matching_patients()

    print("\nExact case property query for 'Sandra'")
    (NewCaseSearchES()
     .set_query(exact_case_property_text_query('first_name', 'Sandra'))
     .matching_patients())

    print("\nStandard analyzed case property query for 'Sandra'")
    pprint(case_property_text_query('first_name', 'Sandra'))
    (NewCaseSearchES()
     .set_query(case_property_text_query('first_name', 'Sandra'))
     .matching_patients())

    print("\nPhonetically analyzed case property query for 'roobinz'")
    pprint(sounds_like_text_query('last_name', 'roobinz'))
    (NewCaseSearchES()
     .set_query(sounds_like_text_query('last_name', 'roobinz'))
     .matching_patients())
