from django.test import SimpleTestCase, override_settings

from corehq.util.es.elasticsearch import Elasticsearch

from .utils import es_test
from ..client import get_client, _elastic_hosts


@override_settings(ELASTICSEARCH_HOSTS=["localhost"],
                   ELASTICSEARCH_PORT=9200)
@es_test
class TestClient(SimpleTestCase):

    def test_elastic_host(self):
        expected = [{"host": "localhost", "port": 9200}]
        self.assertEqual(expected, _elastic_hosts())

    @override_settings(ELASTICSEARCH_HOSTS=["localhost", "otherhost:9292"])
    def test_elastic_hosts(self):
        expected = [
            {"host": "localhost", "port": 9200},
            {"host": "otherhost", "port": 9292},
        ]
        self.assertEqual(expected, _elastic_hosts())

    @override_settings(ELASTICSEARCH_HOSTS=[],
                       ELASTICSEARCH_HOST="otherhost:9292")
    def test_elastic_hosts_fall_back_to_host(self):
        expected = [{"host": "otherhost", "port": 9292}]
        self.assertEqual(expected, _elastic_hosts())

    @override_settings(ELASTICSEARCH_PORT=9292)
    def test_elastic_hosts_alt_default_port(self):
        expected = [{"host": "localhost", "port": 9292}]
        self.assertEqual(expected, _elastic_hosts())

    @override_settings(ELASTICSEARCH_HOSTS=["otherhost:9292"])
    def test_elastic_hosts_alt_host_spec(self):
        expected = [{"host": "otherhost", "port": 9292}]
        self.assertEqual(expected, _elastic_hosts())

    def test_get_client(self):
        self.assertIsInstance(get_client(), Elasticsearch)

    def test_get_client_for_export(self):
        export_client = get_client(for_export=True)
        self.assertIsInstance(export_client, Elasticsearch)
        # depends on memoized client
        self.assertIsNot(export_client, get_client())
