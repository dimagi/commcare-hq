from django.test import SimpleTestCase
from django.http import QueryDict
from urllib.parse import urlparse
from itertools import islice
from tastypie.exceptions import BadRequest
from corehq.apps.api.keyset_paginator import KeysetPaginator


class SequenceQuery:
    def __init__(self, seq):
        self.seq = seq

    def execute(self, limit=None):
        return islice(self.seq, limit)

    @classmethod
    def get_query_params(cls, form):
        return {'next': form}


class KeysetPaginatorTests(SimpleTestCase):

    def test_returns_all_results_below_page_size(self):
        objects = SequenceQuery(range(3))
        paginator = KeysetPaginator({'page_size': 5}, objects, resource_uri='http://test.com/')
        page = paginator.page()
        self.assertEqual(page['objects'], [0, 1, 2])
        self.assertNotIn('next', page['meta'])

    def test_page_includes_next_information_when_more_results_are_available(self):
        objects = SequenceQuery(range(5))
        paginator = KeysetPaginator({'page_size': 3}, objects, resource_uri='http://test.com/')
        page = paginator.page()
        next_args = QueryDict(urlparse(page['meta']['next']).query).dict()
        self.assertEqual(page['objects'], [0, 1, 2])
        self.assertEqual(next_args, {'next': '2', 'page_size': '3'})

    def test_page_fetches_all_results_below_limit(self):
        objects = SequenceQuery(range(5))
        paginator = KeysetPaginator({'limit': 10}, objects)
        page = paginator.page()
        self.assertEqual(page['objects'], [0, 1, 2, 3, 4])
        self.assertEqual(page['meta'], {'limit': 10})
        self.assertNotIn('next', page['meta'])

    def test_no_next_link_is_generated_when_limit_is_reached(self):
        objects = SequenceQuery(range(5))
        paginator = KeysetPaginator({'limit': 3}, objects, resource_uri='http://test.com/')
        page = paginator.page()
        self.assertEqual(page['objects'], [0, 1, 2])
        self.assertNotIn('next', page['meta'])

    def test_page_size_is_used_over_limit_when_smaller(self):
        objects = SequenceQuery(range(10))
        paginator = KeysetPaginator({'page_size': 3, 'limit': 5}, objects, resource_uri='http://test.com/')
        page = paginator.page()
        self.assertEqual(page['objects'], [0, 1, 2])
        self.assertIn('next', page['meta'])

    def test_limit_is_used_over_page_size_when_limit_is_smaller(self):
        objects = SequenceQuery(range(10))
        paginator = KeysetPaginator({'page_size': 5, 'limit': 3}, objects, resource_uri='http://test.com/')
        page = paginator.page()
        self.assertEqual(page['objects'], [0, 1, 2])
        self.assertNotIn('next', page['meta'])

    def test_limits_larger_than_max_pagesize_are_paged(self):
        objects = SequenceQuery(range(5))
        paginator = KeysetPaginator({'limit': 100}, objects, resource_uri='http://test.com/', max_limit=3)
        page = paginator.page()
        next_args = QueryDict(urlparse(page['meta']['next']).query).dict()
        self.assertEqual(page['objects'], [0, 1, 2])
        self.assertEqual(next_args, {'next': '2', 'limit': '97'})

    def test_supports_querydict_request_data(self):
        request_data = QueryDict('page_size=3&some_param=yes')
        objects = SequenceQuery(range(5))
        paginator = KeysetPaginator(request_data, objects, resource_uri='http://test.com/')
        page = paginator.page()
        next_args = QueryDict(urlparse(page['meta']['next']).query).dict()
        self.assertEqual(next_args, {'next': '2', 'page_size': '3', 'some_param': 'yes'})

    def test_defaults_to_page_size_specified_in_settings(self):
        objects = SequenceQuery(range(5))
        paginator = KeysetPaginator({}, objects, resource_uri='http://test.com/')
        with self.settings(API_LIMIT_PER_PAGE=3):
            page = paginator.page()

        self.assertEqual(page['objects'], [0, 1, 2])

    def test_zero_page_size_returns_all_results(self):
        objects = SequenceQuery(range(5))
        paginator = KeysetPaginator({'page_size': 0}, objects, resource_uri='http://test.com/')
        with self.settings(API_LIMIT_PER_PAGE=3):
            page = paginator.page()

        self.assertEqual(page['objects'], [0, 1, 2, 3, 4])

    def test_zero_limit_returns_all_results(self):
        objects = SequenceQuery(range(5))
        paginator = KeysetPaginator({'limit': 0}, objects, resource_uri='http://test.com/', max_limit=0)
        with self.settings(API_LIMIT_PER_PAGE=0):
            page = paginator.page()

        self.assertEqual(page['objects'], [0, 1, 2, 3, 4])

    def test_page_size_beyond_maximum_page_size_returns_max(self):
        objects = SequenceQuery(range(5))
        paginator = KeysetPaginator({'page_size': 0}, objects, resource_uri='http://test.com/', max_limit=3)
        page = paginator.page()

        self.assertEqual(page['objects'], [0, 1, 2])

    def test_negative_page_sizes_are_not_supported(self):
        objects = SequenceQuery(range(5))
        paginator = KeysetPaginator({'page_size': -1}, objects, resource_uri='http://test.com/')
        with self.assertRaises(BadRequest):
            paginator.page()

    def test_negative_limits_are_not_supported(self):
        objects = SequenceQuery(range(5))
        paginator = KeysetPaginator({'limit': -1}, objects, resource_uri='http://test.com/')
        with self.assertRaises(BadRequest):
            paginator.page()

    def test_get_offset_not_implemented(self):
        objects = SequenceQuery(range(5))
        paginator = KeysetPaginator(QueryDict(), objects)

        with self.assertRaises(NotImplementedError):
            paginator.get_offset()

    def test_get_slice_not_implemented(self):
        objects = SequenceQuery(range(5))
        paginator = KeysetPaginator(QueryDict(), objects)

        with self.assertRaises(NotImplementedError):
            paginator.get_slice(limit=10, offset=20)

    def test_get_count_not_implemented(self):
        objects = SequenceQuery(range(5))
        paginator = KeysetPaginator(QueryDict(), objects)

        with self.assertRaises(NotImplementedError):
            paginator.get_count()

    def test_get_previous_not_implemented(self):
        objects = SequenceQuery(range(5))
        paginator = KeysetPaginator(QueryDict(), objects)

        with self.assertRaises(NotImplementedError):
            paginator.get_previous(limit=10, offset=20)
