import uuid
from django.test import SimpleTestCase, override_settings
from corehq.elastic import get_es_new
from corehq.util.elastic import ensure_index_deleted, TEST_ES_PREFIX
from pillowtop.es_utils import get_all_elasticsearch_pillow_classes, get_all_expected_es_indices, \
    ElasticsearchIndexInfo, needs_reindex, create_index_and_set_settings_normal, assume_alias
from pillowtop.tests.utils import TestElasticPillow


class ElasticReindexTest(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        cls.elasticsearch = get_es_new()

    @override_settings(PILLOWTOPS={'test': ['pillowtop.tests.FakePillow']})
    def test_get_all_elastic_pillows_no_match(self):
        self.assertEqual(0, len(get_all_elasticsearch_pillow_classes()))

    @override_settings(PILLOWTOPS={'test': ['pillowtop.tests.test_elasticsearch.TestElasticPillow']})
    def test_get_all_elastic_pillows_match(self):
        es_pillow_classes = get_all_elasticsearch_pillow_classes()
        self.assertEqual(1, len(es_pillow_classes))
        self.assertEqual(TestElasticPillow, es_pillow_classes[0])

    @override_settings(PILLOWTOPS={'test': ['pillowtop.tests.test_elasticsearch.TestElasticPillow']})
    def test_get_all_elastic_indices(self):
        es_indices = list(get_all_expected_es_indices())
        self.assertEqual(1, len(es_indices))
        index_info = es_indices[0]
        self.assertEqual(TestElasticPillow.es_index, index_info.index)
        self.assertEqual(TestElasticPillow.es_alias, index_info.alias)

    def test_needs_reindex_index_missing(self):
        index_info = ElasticsearchIndexInfo(index='should-not-exist', alias='whatever')
        self.assertTrue(needs_reindex(self.elasticsearch, index_info))

    def test_needs_reindex_alias_missing(self):
        index_info = _make_test_index(self.elasticsearch)
        self.assertTrue(needs_reindex(self.elasticsearch, index_info))
        ensure_index_deleted(index_info.index)

    def test_needs_reindex_alias_wrong(self):
        index_info = _make_test_index(self.elasticsearch)
        assume_alias(self.elasticsearch, index_info.index, 'wrong-alias')
        self.assertTrue(needs_reindex(self.elasticsearch, index_info))
        ensure_index_deleted(index_info.index)

    def test_doesnt_need_reindex(self):
        index_info = _make_test_index(self.elasticsearch)
        assume_alias(self.elasticsearch, index_info.index, index_info.alias)
        self.assertFalse(needs_reindex(self.elasticsearch, index_info))
        ensure_index_deleted(index_info.index)


def _make_test_index(es):
    index_name = '{}{}'.format(TEST_ES_PREFIX, uuid.uuid4().hex)
    alias_name = uuid.uuid4().hex
    index_info = ElasticsearchIndexInfo(index=index_name, alias=alias_name)
    create_index_and_set_settings_normal(es, index_name)
    return index_info
