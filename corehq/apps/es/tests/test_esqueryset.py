from unittest import TestCase

from corehq.apps.es.es_query import HQESQuery, ESQuerySet
from corehq.elastic import ESError


class TestESQuerySet(TestCase):
    example_response = {
        u'_shards': {u'failed': 0, u'successful': 5, u'total': 5},
        u'hits': {u'hits': [ {
            u'_id': u'8063dff5-460b-46f2-b4d0-5871abfd97d4',
            u'_index': u'xforms_1cce1f049a1b4d864c9c25dc42648a45',
            u'_score': 1.0,
            u'_type': u'xform',
            u'_source': {
                u'app_id': u'fe8481a39c3738749e6a4766fca99efd',
                u'doc_type': u'xforminstance',
                u'domain': u'mikesproject',
                u'xmlns': u'http://openrosa.org/formdesigner/3a7cc07c-551c-4651-ab1a-d60be3017485'
                }
            },
            {
                u'_id': u'dc1376cd-0869-4c13-a267-365dfc2fa754',
                u'_index': u'xforms_1cce1f049a1b4d864c9c25dc42648a45',
                u'_score': 1.0,
                u'_type': u'xform',
                u'_source': {
                    u'app_id': u'3d622620ca00d7709625220751a7b1f9',
                    u'doc_type': u'xforminstance',
                    u'domain': u'mikesproject',
                    u'xmlns': u'http://openrosa.org/formdesigner/54db1962-b938-4e2b-b00e-08414163ead4'
                    }
                }
            ],
            u'max_score': 1.0,
            u'total': 5247
            },
        u'timed_out': False,
        u'took': 4
    }
    example_error = {u'error': u'IndexMissingException[[xforms_123jlajlaf] missing]',
             u'status': 404}

    def test_response(self):
        hits = [
            {
                u'app_id': u'fe8481a39c3738749e6a4766fca99efd',
                u'doc_type': u'xforminstance',
                u'domain': u'mikesproject',
                u'xmlns': u'http://openrosa.org/formdesigner/3a7cc07c-551c-4651-ab1a-d60be3017485'
            },
            {
                u'app_id': u'3d622620ca00d7709625220751a7b1f9',
                u'doc_type': u'xforminstance',
                u'domain': u'mikesproject',
                u'xmlns': u'http://openrosa.org/formdesigner/54db1962-b938-4e2b-b00e-08414163ead4'
            }
        ]
        fields = [u'app_id', u'doc_type', u'domain', u'xmlns']
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
            u'hits': {u'hits': [{
                u'_source': {
                    u'domains': [u'joesproject'],
                    }
                },
                {
                    u'_source': {
                        u'domains': [u'mikesproject']
                        }
                    }
                ],
            },
        }

        hits = [
            {
                u'domains': u'joesproject',
            },
            {
                u'domains': u'mikesproject',
            }
        ]
        fields = [u'domain']
        response = ESQuerySet(
            example_response,
            HQESQuery('forms').fields(fields)
        )
        self.assertEquals(response.hits, hits)
