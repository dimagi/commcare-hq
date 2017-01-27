from django.test import SimpleTestCase

from corehq.util.test_utils import generate_cases
from corehq.apps.es.utils import chunk_query
from corehq.apps.es.forms import FormES


QUERY = {
  'sort': [
    {
      'received_on': {
        'order': 'asc'
      }
    }
  ],
  'query': {
    'filtered': {
      'filter': {
        'and': [
          {
            'term': {
              'domain.exact': u'aspace'
            }
          },
          {
            'term': {
              'app_id': u'09fe257a198ad1ae109ed627ed847ee9'
            }
          },
          {
            'term': {
              'xmlns.exact': u'http://openrosa.org/formdesigner/11FAC65A-F2CD-427F-A870-CF126336AAB5'
            }
          },
          {
            'or': {
              'terms': {
                'form.meta.userID': [
                  u'51cd680c0bd1c21bb5e63dab99748248',
                  u'38b858717522c898e37f6239eda0ba5a'
                ]
              }
            },
          },
          {
            'range': {
              'received_on': {
                'lt': '2017-01-28T00:00:00+07:00',
                'gte': '2015-01-27T00:00:00+07:00'
              }
            }
          }
        ]
      },
      'query': {
            'match_all': {
        }
      }
    }
  }
}


class TestChunkQuery(SimpleTestCase):
    '''
    Tests the ability to chunk ES queries based on a term
    '''

    def test_chunking_size(self):
        form_es_query = FormES()
        form_es_query.es_query = QUERY

        queries = chunk_query(form_es_query, 'form.meta.userID', chunk_size=1)
        ids = queries[0].es_query['query']['filtered']['filter']['and'][3]['or']['terms']['form.meta.userID']
        self.assertEqual(len(ids), 1)

        ids = queries[1].es_query['query']['filtered']['filter']['and'][3]['or']['terms']['form.meta.userID']
        self.assertEqual(len(ids), 1)

        queries = chunk_query(form_es_query, 'form.meta.userID', chunk_size=10)
        ids = queries[0].es_query['query']['filtered']['filter']['and'][3]['or']['terms']['form.meta.userID']
        self.assertEqual(len(ids), 2)


@generate_cases([
    ([QUERY, 'form.meta.userID'], 2),
    ([QUERY, 'xmlns.exact'], 1),
    ([QUERY, 'does-not-exist'], 1),
], TestChunkQuery)
def test_chunk_query(self, chunk_query_args, expected_number_of_queries):
    form_es_query = FormES()
    form_es_query.es_query = chunk_query_args[0]
    chunk_query_args[0] = form_es_query
    self.assertEqual(len(chunk_query(*chunk_query_args, chunk_size=1)), expected_number_of_queries)
