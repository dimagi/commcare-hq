from unittest import TestCase

from corehq.apps.es.es_query import HQESQuery, ESQuerySet
from corehq.elastic import ESError


class TestESQuerySet(TestCase):
    example_response = {
        '_shards': {'failed': 0, 'successful': 5, 'total': 5},
        'hits': {'hits': [ {
            '_id': '8063dff5-460b-46f2-b4d0-5871abfd97d4',
            '_index': 'xforms_1cce1f049a1b4d864c9c25dc42648a45',
            '_score': 1.0,
            '_type': 'xform',
            '_source': {
                'app_id': 'fe8481a39c3738749e6a4766fca99efd',
                'doc_type': 'xforminstance',
                'domain': 'mikesproject',
                'xmlns': 'http://openrosa.org/formdesigner/3a7cc07c-551c-4651-ab1a-d60be3017485'
                }
            },
            {
                '_id': 'dc1376cd-0869-4c13-a267-365dfc2fa754',
                '_index': 'xforms_1cce1f049a1b4d864c9c25dc42648a45',
                '_score': 1.0,
                '_type': 'xform',
                '_source': {
                    'app_id': '3d622620ca00d7709625220751a7b1f9',
                    'doc_type': 'xforminstance',
                    'domain': 'mikesproject',
                    'xmlns': 'http://openrosa.org/formdesigner/54db1962-b938-4e2b-b00e-08414163ead4'
                    }
                }
            ],
            'max_score': 1.0,
            'total': 5247
            },
        'timed_out': False,
        'took': 4
    }
    example_error = {'error': 'IndexMissingException[[xforms_123jlajlaf] missing]',
             'status': 404}

    def test_response(self):
        hits = [
            {
                'app_id': 'fe8481a39c3738749e6a4766fca99efd',
                'doc_type': 'xforminstance',
                'domain': 'mikesproject',
                'xmlns': 'http://openrosa.org/formdesigner/3a7cc07c-551c-4651-ab1a-d60be3017485'
            },
            {
                'app_id': '3d622620ca00d7709625220751a7b1f9',
                'doc_type': 'xforminstance',
                'domain': 'mikesproject',
                'xmlns': 'http://openrosa.org/formdesigner/54db1962-b938-4e2b-b00e-08414163ead4'
            }
        ]
        fields = ['app_id', 'doc_type', 'domain', 'xmlns']
        response = ESQuerySet(
            self.example_response,
            HQESQuery('forms').fields(fields)
        )
        self.assertEquals(response.total, 5247)
        self.assertEquals(response.hits, hits)

    def test_error(self):
        with self.assertRaises(ESError):
            ESQuerySet(self.example_error, HQESQuery('forms'))

    def test_flatten_field_dicts(self):
        example_response = {
            'hits': {'hits': [{
                '_source': {
                    'domains': ['joesproject'],
                    }
                },
                {
                    '_source': {
                        'domains': ['mikesproject']
                        }
                    }
                ],
            },
        }

        hits = [
            {
                'domains': 'joesproject',
            },
            {
                'domains': 'mikesproject',
            }
        ]
        fields = ['domain']
        response = ESQuerySet(
            example_response,
            HQESQuery('forms').fields(fields)
        )
        self.assertEquals(response.hits, hits)

    def test_exclude_source(self):
        hits = ['8063dff5-460b-46f2-b4d0-5871abfd97d4', 'dc1376cd-0869-4c13-a267-365dfc2fa754']
        response = ESQuerySet(
            self.example_response,
            HQESQuery('forms').exclude_source()
        )
        self.assertEquals(response.hits, hits)
