from django.test import SimpleTestCase, override_settings

from corehq.apps.change_feed.connection import get_kafka_client


class TestKafkaConnection(SimpleTestCase):

    @override_settings(KAFKA_API_VERSION=(3, 2, 3))
    def test_get_kafka_client_with_api_version(self):
        with get_kafka_client() as client:  # should not raise
            client.poll()
