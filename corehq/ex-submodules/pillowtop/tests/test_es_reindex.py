from django.test import SimpleTestCase, override_settings
from pillowtop.es_utils import get_all_elasticsearch_pillow_classes, get_all_expected_es_indices
from pillowtop.tests.utils import TestElasticPillow


class ElasticReindexTest(SimpleTestCase):

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
