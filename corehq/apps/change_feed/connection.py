from __future__ import absolute_import
from __future__ import unicode_literals

from django.conf import settings
from kafka.client import KafkaClient


GENERIC_KAFKA_CLIENT_ID = 'cchq-kafka-client'


def get_kafka_client(client_id=GENERIC_KAFKA_CLIENT_ID):
    return KafkaClient(
        bootstrap_servers=settings.KAFKA_BROKERS,
        client_id=client_id
    )
