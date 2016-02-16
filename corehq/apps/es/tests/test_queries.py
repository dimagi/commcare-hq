import json
from unittest import TestCase

from corehq.apps.es.es_query import HQESQuery


class TestQueries(TestCase):
    def assertHasQuery(self, es_query, desired_query):
        generated = es_query.raw_query['query']['filtered']['query']
        msg = "Expected to find query\n{}\nInstead found\n{}".format(
            json.dumps(desired_query, indent=4),
            json.dumps(generated, indent=4),
        )
        self.assertEqual(generated, desired_query, msg=msg)

    def test_query(self):
        query = HQESQuery('forms').set_query({"fancy_query": {"foo": "bar"}})
        self.assertHasQuery(query, {"fancy_query": {"foo": "bar"}})

    def test_null_query_string_queries(self):
        query = HQESQuery('forms').search_string_query("")
        self.assertHasQuery(query, {"match_all": {}})

        query = HQESQuery('forms').search_string_query(None)
        self.assertHasQuery(query, {"match_all": {}})

    def test_basic_query_string_query(self):
        query = HQESQuery('forms').search_string_query("foo")
        self.assertHasQuery(query, {
            "query_string": {
                "query": "*foo*",
                "default_operator": "AND",
                "fields": None,
            }
        })

    def test_query_with_fields(self):
        default_fields = ['name', 'type', 'date']
        query = HQESQuery('forms').search_string_query("foo", default_fields)
        self.assertHasQuery(query, {
            "query_string": {
                "query": "*foo*",
                "default_operator": "AND",
                "fields": ['name', 'type', 'date'],
            }
        })

    def test_complex_query_with_fields(self):
        default_fields = ['name', 'type', 'date']
        query = (HQESQuery('forms')
                 .search_string_query("name: foo", default_fields))
        self.assertHasQuery(query, {
            "query_string": {
                "query": "name: foo",
                "default_operator": "AND",
                "fields": None,
            }
        })
