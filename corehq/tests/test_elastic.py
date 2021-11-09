import uuid

from contextlib import contextmanager
from django.test import SimpleTestCase

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
        """Test that all results are returned in very large scroll queries.

        NOTE: this test is slow (~7sec on an i7-10610U)

        Due to the slowness, this test indexes docs discretely rather than
        using the `_index_test_docs()` helper in order to be more performant.

        The combination of the following optimizations:

        - Convert test setup/teardown to functions instead of classmethods
          to allow this test to not clean up after itself (tearDown deletes
          the entire index).
        - Discrete document indexing in this method rather than using a
          contextmanager that deletes the docs after the test completes.
        - Calling `indices.refresh(...)` once after all docs are indexed rather
          than specifying a refresh after each doc is indexed.

        reduced the runtime of this test from ~25sec to ~7sec.
        """
        docs = []
        interface = ElasticsearchInterface(self.es)
        for integer in range((interface.SCROLL_SIZE * 2) + 1):
            doc_id = uuid.uuid4().hex
            doc = {"_id": doc_id, "number": integer}
            interface.index_doc(self.index, self.doc_type, doc_id, doc)
            docs.append(doc)
        self.es.indices.refresh(self.index)
        results = []
        for result in scroll_query(self.index, {}):
            results.append(result["_source"])
        results.sort(key=lambda d: d["number"])
        self.assertEqual(results, docs)

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
