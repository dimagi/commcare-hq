import uuid

from contextlib import contextmanager
from django.test import SimpleTestCase

from corehq.apps.es.tests.utils import es_test
from corehq.elastic import get_es_new, scroll_query
from corehq.util.es.interface import ElasticsearchInterface
from corehq.util.es.tests.util import (
    TEST_ES_ALIAS,
    TEST_ES_MAPPING,
    TEST_ES_TYPE,
    deregister_test_meta,
    register_test_meta,
)


@es_test
class TestElastic(SimpleTestCase):

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
                # pop _id because scan() doesn't inject that (yet)
                indexed[result["_id"]].pop("_id")
                self.assertEqual(result["_source"], indexed[result["_id"]])
            self.assertEqual(len(results), len(indexed))

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
