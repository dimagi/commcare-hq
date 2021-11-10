import uuid

from contextlib import contextmanager
from django.test import SimpleTestCase
from mock import patch

from corehq.apps.es.tests.utils import (
    TEST_ES_INFO,
    TEST_ES_MAPPING,
    es_test,
)
from corehq.elastic import get_es_new, scroll_query
from corehq.util.es.interface import ElasticsearchInterface


@es_test(index=TEST_ES_INFO)
class TestElastic(SimpleTestCase):

    def setUp(self):
        super().setUp()
        self.index = TEST_ES_INFO.alias
        self.doc_type = TEST_ES_INFO.type
        self.es = get_es_new()
        meta = {"mapping": TEST_ES_MAPPING}
        if not self.es.indices.exists(self.index):
            self.es.indices.create(index=self.index, body=meta)

    def tearDown(self):
        super().tearDown()
        self.es.indices.delete(self.index)

    def test_scroll_query_accept_size_and_scroll_kw(self):
        list(scroll_query(self.index, {}, size=1, scroll="1m"))

    def test_scroll_query_invalid_kw(self):
        with self.assertRaises(ValueError):
            list(scroll_query(self.index, {}, doc_type=self.doc_type))

    def test_scroll_query_scroll_size(self):
        total_docs = 3
        docs = [{"number": n} for n in range(total_docs)]
        with self._index_test_docs(self.index, self.doc_type, docs):
            with patch("corehq.elastic.ElasticsearchInterface.scroll",
                       side_effect=self.es.scroll) as scroll:
                list(scroll_query(self.index, {}, size=1))
                # NOTE: call_count == total_docs because the final call returns
                # empty, resulting in StopIteration.
                # Call sequence (for 3 total docs with size=1):
                # - len(iface.search(...)["hits"]["hits"]) == 1
                # - len(iface.scroll(...)["hits"]["hits"]) == 1
                # - len(iface.scroll(...)["hits"]["hits"]) == 1
                # - len(iface.scroll(...)["hits"]["hits"]) == 0
                self.assertEqual(scroll.call_count, total_docs)

    def test_scroll_query(self):
        docs = [
            {"prop": "port", "color": "red"},
            {"prop": "starboard", "color": "green"},
        ]
        with self._index_test_docs(self.index, self.doc_type, docs) as indexed:
            results = []
            for result in scroll_query(self.index, {}):
                results.append(result)
                self.assertIn(result["_id"], indexed)
                self.assertEqual(result["_source"], indexed[result["_id"]])
            self.assertEqual(len(results), len(indexed))

    def test_scroll_query_returns_over_2x_size_docs(self):
        """Test that all results are returned for scroll queries."""
        scroll_size = 3  # fetch N docs per "scroll"
        total_docs = (scroll_size * 2) + 1
        docs = [{"number": n} for n in range(total_docs)]
        with self._index_test_docs(self.index, self.doc_type, docs) as indexed:
            self.assertEqual(len(indexed), total_docs)
            results = {}
            for result in scroll_query(self.index, {}, size=scroll_size):
                results[result["_id"]] = result["_source"]
        self.assertEqual(results, indexed)

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
