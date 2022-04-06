import uuid

from django.test import SimpleTestCase

from corehq.apps.es.tests.utils import TEST_ES_INFO, es_test
from corehq.elastic import get_es_new
from corehq.util.es.interface import ElasticsearchInterface

from ..utils import fetch_elastic_mapping, sorted_mapping


@es_test
class TestMappingsUtilsNoIndex(SimpleTestCase):

    def test_sorted_mapping(self):
        expected_order = ["alpha", "items", "zulu", "properties"]
        unsorted = {key: None for key in expected_order[::-1]}
        mapping = unsorted.copy()
        mapping["items"] = [unsorted.copy()]
        mapping["properties"] = unsorted.copy()
        mapping = sorted_mapping(mapping)
        self.assertEqual(expected_order, list(mapping))
        self.assertEqual(expected_order, list(mapping["items"][0]))
        self.assertEqual(expected_order, list(mapping["properties"]))


@es_test(index=TEST_ES_INFO)
class TestMappingsUtilsWithIndex(SimpleTestCase):

    def setUp(self):
        self.index = TEST_ES_INFO.alias
        self.doc_type = TEST_ES_INFO.type
        self.es = get_es_new()
        # tweak mapping
        self.mapping = {"properties": {"message": {"type": "string"}}}
        meta = {"mapping": self.mapping}
        # setup index
        if self.es.indices.exists(self.index):
            self.es.indices.delete(self.index)
        self.es.indices.create(index=self.index, body=meta)

        # insert a doc so we get some mapping data
        interface = ElasticsearchInterface(self.es)
        ident = uuid.uuid4().hex
        doc = {"message": "hello"}
        interface.index_doc(self.index, self.doc_type, ident, doc)
        self.es.indices.refresh(self.index)

    def tearDown(self):
        super().tearDown()
        self.es.indices.delete(self.index)

    def test_fetch_elastic_mapping(self):
        from_elastic = fetch_elastic_mapping(self.index, self.doc_type)
        self.assertEqual(self.mapping, from_elastic)
