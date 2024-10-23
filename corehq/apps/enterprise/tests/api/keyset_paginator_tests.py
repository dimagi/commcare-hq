from django.test import SimpleTestCase
from django.http import QueryDict
from corehq.apps.enterprise.resumable_iterator_wrapper import ResumableIteratorWrapper
from corehq.apps.enterprise.api.keyset_paginator import KeysetPaginator


class SequenceWrapper:
    def __init__(self, seq, get_next_fn=None):
        self.seq = seq
        self.get_next_fn = get_next_fn

    def execute(self, limit=None):
        return ResumableIteratorWrapper(lambda _: self.seq, self.get_next_fn, limit=limit)


class KeysetPaginatorTests(SimpleTestCase):
    def test_page_fetches_all_results_below_limit(self):
        objects = SequenceWrapper(range(5))
        paginator = KeysetPaginator(QueryDict(), objects, limit=10)
        page = paginator.page()
        self.assertEqual(page['objects'], [0, 1, 2, 3, 4])
        self.assertEqual(page['meta'], {'limit': 10})

    def test_page_includes_next_information_when_more_results_are_available(self):
        objects = SequenceWrapper(range(5), lambda ele: {'next': ele})
        paginator = KeysetPaginator(QueryDict(), objects, resource_uri='http://test.com/', limit=3)
        page = paginator.page()
        self.assertEqual(page['objects'], [0, 1, 2])
        self.assertEqual(page['meta'], {'limit': 3, 'next': 'http://test.com/?limit=3&next=2'})

    def test_does_not_include_duplicate_limits(self):
        request_data = QueryDict(mutable=True)
        request_data['limit'] = 3
        objects = SequenceWrapper(range(5), lambda ele: {'next': ele})
        paginator = KeysetPaginator(request_data, objects, resource_uri='http://test.com/')
        page = paginator.page()
        self.assertEqual(page['meta']['next'], 'http://test.com/?limit=3&next=2')

    def test_supports_dict_request_data(self):
        request_data = {
            'limit': 3,
            'some_param': 'yes'
        }
        objects = SequenceWrapper(range(5), lambda ele: {'next': ele})
        paginator = KeysetPaginator(request_data, objects, resource_uri='http://test.com/')
        page = paginator.page()
        self.assertEqual(page['meta']['next'], 'http://test.com/?limit=3&some_param=yes&next=2')

    def test_get_offset_not_implemented(self):
        objects = SequenceWrapper(range(5))
        paginator = KeysetPaginator(QueryDict(), objects)

        with self.assertRaises(NotImplementedError):
            paginator.get_offset()

    def test_get_slice_not_implemented(self):
        objects = SequenceWrapper(range(5))
        paginator = KeysetPaginator(QueryDict(), objects)

        with self.assertRaises(NotImplementedError):
            paginator.get_slice(limit=10, offset=20)

    def test_get_count_not_implemented(self):
        objects = SequenceWrapper(range(5))
        paginator = KeysetPaginator(QueryDict(), objects)

        with self.assertRaises(NotImplementedError):
            paginator.get_count()

    def test_get_previous_not_implemented(self):
        objects = SequenceWrapper(range(5))
        paginator = KeysetPaginator(QueryDict(), objects)

        with self.assertRaises(NotImplementedError):
            paginator.get_previous(limit=10, offset=20)
