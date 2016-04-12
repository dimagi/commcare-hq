import uuid
from django.test import SimpleTestCase, override_settings
from corehq.elastic import get_es_new
from corehq.util.elastic import TEST_ES_PREFIX
from pillowtop.es_utils import get_all_elasticsearch_pillow_classes, get_all_inferred_es_indices_from_pillows, \
    ElasticsearchIndexInfo, create_index_and_set_settings_normal
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
    def test_get_all_elastic_indices_from_pillows(self):
        es_indices = list(get_all_inferred_es_indices_from_pillows())
        self.assertEqual(1, len(es_indices))
        index_info = es_indices[0]
        self.assertEqual(TestElasticPillow.es_index, index_info.index)
        self.assertEqual(TestElasticPillow.es_alias, index_info.alias)
        self.assertEqual(TestElasticPillow.es_type, index_info.type)


def _make_test_index(es):
    index_name = '{}{}'.format(TEST_ES_PREFIX, uuid.uuid4().hex)
    alias_name = uuid.uuid4().hex
    index_info = ElasticsearchIndexInfo(index=index_name, alias=alias_name)
    create_index_and_set_settings_normal(es, index_name)
    return index_info
