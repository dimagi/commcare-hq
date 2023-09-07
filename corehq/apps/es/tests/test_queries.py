import json
from unittest import TestCase

from nose.tools import assert_equal, assert_raises

from couchforms.geopoint import GeoPoint

from corehq.apps.es.es_query import HQESQuery
from corehq.apps.es.queries import geo_distance, match


class TestQueries(TestCase):

    def assertHasQuery(self, es_query, desired_query):
        generated = es_query._query
        msg = "Expected to find query\n{}\nInstead found\n{}".format(
            json.dumps(desired_query, indent=4),
            json.dumps(generated, indent=4),
        )
        self.assertEqual(generated, desired_query, msg=msg)

    def test_query(self):
        query = HQESQuery('forms').set_query({"fancy_query": {"foo": "bar"}})
        self.assertHasQuery(query, {"fancy_query": {"foo": "bar"}})

    def test_null_query_string_queries(self):
        query = HQESQuery('forms').search_string_query("", ["name"])
        self.assertHasQuery(query, {"match_all": {}})

        query = HQESQuery('forms').search_string_query(None, ["name"])
        self.assertHasQuery(query, {"match_all": {}})

    def test_basic_query_string_query(self):
        query = HQESQuery('forms').search_string_query("foo", ["name"])
        self.assertHasQuery(query, {
            "query_string": {
                "query": "*foo*",
                "default_operator": "AND",
                "fields": ["name"],
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
        # complex queries should be flattened to individual search terms to avoid potential ES injection
        default_fields = ['name', 'type', 'date']
        query = (HQESQuery('forms')
                 .search_string_query("name: foo", default_fields))
        self.assertHasQuery(query, {
            "query_string": {
                "query": "*name* *foo*",
                "default_operator": "AND",
                "fields": ['name', 'type', 'date'],
            }
        })

    def test_match_raises_with_invalid_operator(self):
        with self.assertRaises(ValueError):
            match("cyrus", "pet_name", operator="And")


def test_valid_geo_distance():
    assert_equal(
        geo_distance('gps_location', GeoPoint(-33.1, 151.8), kilometers=100),
        {
            'geo_distance': {
                'gps_location': {
                    'lat': -33.1,
                    'lon': 151.8
                },
                'distance': '100kilometers',
            }
        }
    )


def test_invalid_geo_distance():
    with assert_raises(ValueError):
        geo_distance('gps_location', GeoPoint(-33.1, 151.8), smoots=100)
