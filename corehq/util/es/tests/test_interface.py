import uuid
from unittest.mock import patch

from contextlib import contextmanager
from django.test import SimpleTestCase

from corehq.apps.es.tests.utils import (
    TEST_ES_INFO,
    TEST_ES_MAPPING,
    es_test,
)
from corehq.elastic import get_es_new
from corehq.util.es.interface import ElasticsearchInterface


@es_test(index=TEST_ES_INFO, setup_class=True)
class TestESInterface(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.index = TEST_ES_INFO.alias
        cls.doc_type = TEST_ES_INFO.type
        cls.es = get_es_new()
        meta = {"mapping": TEST_ES_MAPPING}
        if not cls.es.indices.exists(cls.index):
            cls.es.indices.create(index=cls.index, body=meta)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.es.indices.delete(cls.index)

    def _validate_es_scroll_search_params(self, scroll_query, search_query):
        """Call ElasticsearchInterface.iter_scroll() and test that the resulting
        API search parameters match what we expect.

        Notably:
        - Search call does not include the `search_type='scan'`.
        - Calling `iter_scroll(..., body=scroll_query)` results in an API call
          where `body == search_query`.
        """
        interface = ElasticsearchInterface(self.es)
        scroll_kw = {
            "doc_type": self.doc_type,
            "params": {},
            "scroll": "1m",
            "size": 10,
        }
        with patch.object(self.es, "search", return_value={}) as search:
            list(interface.iter_scroll(self.index, body=scroll_query, **scroll_kw))
            search.assert_called_once_with(index=self.index, body=search_query, **scroll_kw)

    def test_scroll_no_searchtype_scan(self):
        """Tests that search_type='scan' is not added to the search parameters"""
        self._validate_es_scroll_search_params({}, {"sort": "_doc"})

    def test_scroll_query_extended(self):
        """Tests that sort=_doc is added to an non-empty query"""
        self._validate_es_scroll_search_params({"_id": "abc"},
                                             {"_id": "abc", "sort": "_doc"})

    def test_scroll_query_sort_safe(self):
        """Tests that a provided a `sort` query will not be overwritten"""
        self._validate_es_scroll_search_params({"sort": "_id"}, {"sort": "_id"})

    def test_search_and_scroll_yield_same_docs(self):
        # some documents for querying
        docs = [
            {"prop": "centerline", "prop_count": 1},
            {"prop": "starboard", "prop_count": 2},
        ]
        with self._index_test_docs(self.index, self.doc_type, docs) as indexed:

            def search_query():
                """Perform a search query"""
                return interface.search(self.index, self.doc_type)["hits"]["hits"]

            def scroll_query():
                """Perform a scroll query"""
                for results in interface.iter_scroll(self.index, self.doc_type):
                    for hit in results["hits"]["hits"]:
                        yield hit

            interface = ElasticsearchInterface(self.es)
            for results_getter in [search_query, scroll_query]:
                results = {}
                for hit in results_getter():
                    results[hit["_id"]] = hit
                self.assertEqual(len(indexed), len(results))
                for doc_id, doc in indexed.items():
                    self.assertIn(doc_id, results)
                    self.assertEqual(self.doc_type, results[doc_id]["_type"])
                    for attr in doc:
                        self.assertEqual(doc[attr], results[doc_id]["_source"][attr])

    def test_scroll_ambiguous_size_raises(self):
        interface = ElasticsearchInterface(self.es)
        query = {"size": 1}
        with self.assertRaises(ValueError):
            list(interface.iter_scroll(self.index, self.doc_type, query, size=1))

    def test_scroll_query_size_as_keyword(self):
        docs = [{"number": n} for n in range(3)]
        with self._index_test_docs(self.index, self.doc_type, docs):
            self._test_scroll_backend_calls({}, len(docs), size=1)

    def test_scroll_query_size_in_query(self):
        docs = [{"number": n} for n in range(3)]
        with self._index_test_docs(self.index, self.doc_type, docs):
            self._test_scroll_backend_calls({"size": 1}, len(docs))

    def test_scroll_size_default(self):
        docs = [{"number": n} for n in range(3)]
        interface = ElasticsearchInterface(self.es)
        interface.SCROLL_SIZE = 1
        with self._index_test_docs(self.index, self.doc_type, docs):
            self._test_scroll_backend_calls({}, len(docs), interface)

    def _test_scroll_backend_calls(self, query, call_count, interface=None, **iter_scroll_kw):
        if interface is None:
            interface = ElasticsearchInterface(self.es)
        with patch.object(interface, "search", side_effect=self.es.search) as search, \
             patch.object(interface, "scroll", side_effect=self.es.scroll) as scroll:
            list(interface.iter_scroll(self.index, self.doc_type, query, **iter_scroll_kw))
            # NOTE: scroll.call_count == call_count because the final scroll
            # call returns zero hits (thus ending the generator).
            # Call sequence (for 3 matched docs with size=1):
            # - len(interface.search(...)["hits"]["hits"]) == 1
            # - len(interface.scroll(...)["hits"]["hits"]) == 1
            # - len(interface.scroll(...)["hits"]["hits"]) == 1
            # - len(interface.scroll(...)["hits"]["hits"]) == 0
            search.assert_called_once()
            self.assertEqual(scroll.call_count, call_count)

    @contextmanager
    def _index_test_docs(self, index, doc_type, docs):
        interface = ElasticsearchInterface(self.es)
        indexed = {}
        for doc in docs:
            doc_id = doc.get("_id")
            if doc_id is None:
                doc = dict(doc)  # make a copy
                doc_id = doc["_id"] = uuid.uuid4().hex
            indexed[doc_id] = doc
            interface.index_doc(index, doc_type, doc_id, doc)
        self.es.indices.refresh(index)
        try:
            yield indexed
        finally:
            for doc_id in indexed:
                self.es.delete(index, doc_type, doc_id)
            self.es.indices.refresh(index)
