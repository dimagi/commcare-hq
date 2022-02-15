import uuid
from django.test import SimpleTestCase

from corehq.apps.es.tests.utils import TEST_ES_INFO, es_test
from corehq.elastic import get_es_new
from corehq.util.es.interface import ElasticsearchInterface

from .utils import fetch_elastic_mapping
#from ..user_mapping import USER_INDEX_INFO


@es_test(index=TEST_ES_INFO)
class TestMappingsTestUtils(SimpleTestCase):

    def setUp(self):
        super().setUp()
        self.alias = TEST_ES_INFO.alias
        self.doc_type = TEST_ES_INFO.type
        self.es = get_es_new()
        # tweak mapping
        self.mapping = {"properties": {"message": {"type": "string"}}}
        meta = {"mapping": self.mapping}
        # setup index
        if self.es.indices.exists(self.alias):
            self.es.indices.delete(self.alias)
        self.es.indices.create(index=self.alias, body=meta)

        # insert a doc so we get some mapping data
        interface = ElasticsearchInterface(self.es)
        ident = uuid.uuid4().hex
        doc = {"message": "hello"}
        interface.index_doc(self.alias, self.doc_type, ident, doc)
        self.es.indices.refresh(self.alias)

    def tearDown(self):
        super().tearDown()
        self.es.indices.delete(self.alias)

    def test_fetch_elastic_mapping(self):
        from_elastic = fetch_elastic_mapping(self.alias, self.doc_type)
        self.assertEqual(self.mapping, from_elastic)
