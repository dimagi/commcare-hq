from datetime import datetime

from django.test import TestCase
from custom.bihar.reports.due_list import get_due_list_by_task_name, get_due_list_records


class FakeES(object):
    """
    A mock of ES that will return the docs that have been
    added regardless of the query, and some hardcoded
    facets just to sanity check the facet handling code
    """
    
    def __init__(self):
        self.docs = []

    def add_doc(self, id, doc):
        self.docs.append(doc)

    def base_query(self, start=0, size=None):
        return {'filter': {'and': []}}
    
    def run_query(self, query, es_type=None):
        return {
            'hits': {
                'total': len(self.docs),
                'hits': [{'_source': doc} for doc in self.docs]
            },
            'facets': {
                'vaccination_names': {
                    'terms': [
                        {'term': 'foo', 'count': 10}
                    ]
                }
            }
        }


class TestDueList(TestCase):
    """
    Tests the Due List function superficially 
    """
    
    def test_due_list_by_task_name(self):
        '''
        Basic sanity check that the function does not crash and decomposes
        the facet properly
        '''
        es = FakeES()
        due_list = list(get_due_list_by_task_name(datetime.utcnow(), case_es=es))
        self.assertEquals(due_list, [('foo', 10)])


    def test_get_due_list_records(self):
        '''
        Basic sanity check that the function does not crash and decomposes
        the records properly
        '''
        es = FakeES()
        es.add_doc('foozle', {'foo': 'bar'})
        es.add_doc('boozle', {'fizzle': 'bizzle'})
        due_list_records = list(get_due_list_records(datetime.utcnow(), case_es=es))
        self.assertEquals(due_list_records, [{'foo': 'bar'}, {'fizzle': 'bizzle'}])
