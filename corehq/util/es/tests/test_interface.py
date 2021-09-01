import uuid

from contextlib import contextmanager
from django.test import SimpleTestCase
from mock import ANY, patch

from corehq.apps.es.tests.utils import es_test
from corehq.elastic import SerializationError, get_es_new
from corehq.util.es.interface import ElasticsearchInterface
from corehq.util.es.tests.util import (
    TEST_ES_ALIAS,
    TEST_ES_MAPPING,
    TEST_ES_TYPE,
    deregister_test_meta,
    register_test_meta,
)


@es_test
class TestESInterface(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        register_test_meta()
        cls.index = TEST_ES_ALIAS
        cls.doc_type = TEST_ES_TYPE
        cls.es = get_es_new()
        meta = {"mapping": TEST_ES_MAPPING}
        if not cls.es.indices.exists(cls.index):
            cls.es.indices.create(index=cls.index, body=meta)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.es.indices.delete(cls.index)
        deregister_test_meta()

    def _validate_es_scan_search_params(self, scan_query, search_query):
        """Call ElasticsearchInterface.scan() and test that the resulting API
        search parameters match what we expect.

        Notably:
        - Search call does not include the `search_type='scan'`.
        - Calling `scan(..., query=scan_query, ...)` results in an API call
          where `body == search_query`.
        """
        interface = ElasticsearchInterface(self.es)
        skw = {
            "index": "et",
            "doc_type": "al",
            "request_timeout": ANY,
            "scroll": ANY,
            "size": ANY,
        }
        with patch.object(self.es, "search") as search:
            try:
                list(interface.scan(skw["index"], scan_query, skw["doc_type"]))
            except SerializationError:
                # fails to serialize the Mock object.
                pass
            search.assert_called_once_with(body=search_query, **skw)

    def test_scan_no_searchtype_scan(self):
        """Tests that search_type='scan' is not added to the search parameters"""
        self._validate_es_scan_search_params({}, {"sort": "_doc"})

    def test_scan_query_extended(self):
        """Tests that sort=_doc is added to an non-empty query"""
        self._validate_es_scan_search_params({"_id": "abc"},
                                             {"_id": "abc", "sort": "_doc"})

    def test_scan_query_sort_safe(self):
        """Tests that a provided a `sort` query will not be overwritten"""
        self._validate_es_scan_search_params({"sort": "_id"}, {"sort": "_id"})

    def test_search_and_scan_yield_same_docs(self):
        # some documents for querying
        docs = [
            {"prop": "centerline", "prop_count": 1},
            {"prop": "starboard", "prop_count": 2},
        ]
        with self._index_test_docs(self.index, self.doc_type, docs) as indexed:

            def search_query():
                """Perform a search query"""
                return interface.search(self.index, self.doc_type)["hits"]["hits"]

            def scan_query():
                """Perform a scan query"""
                return interface.scan(self.index, {}, self.doc_type)

            interface = ElasticsearchInterface(self.es)
            for results_getter in [search_query, scan_query]:
                results = {}
                for hit in results_getter():
                    results[hit["_id"]] = hit
                self.assertEqual(len(indexed), len(results))
                for doc_id, doc in indexed.items():
                    self.assertIn(doc_id, results)
                    self.assertEqual(self.doc_type, results[doc_id]["_type"])
                    for attr in doc:
                        self.assertEqual(doc[attr], results[doc_id]["_source"][attr])

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
            interface.index_doc(index, doc_type, doc_id, doc,
                                params={"refresh": True})
        try:
            yield indexed
        finally:
            for doc_id in indexed:
                self.es.delete(index, doc_type, doc_id)
