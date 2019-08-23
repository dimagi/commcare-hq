from __future__ import absolute_import
from __future__ import unicode_literals

from django.conf import settings
from kafka.client import KafkaClient
from kafka.client import SimpleClient

from corehq.util.io import ClosingContextProxy

GENERIC_KAFKA_CLIENT_ID = 'cchq-kafka-client'


def get_simple_kafka_client(client_id=GENERIC_KAFKA_CLIENT_ID):
    # this uses the old SimpleClient because we are using the old SimpleProducer interface
    return ClosingContextProxy(SimpleClient(
        hosts=settings.KAFKA_BROKERS,
        client_id=client_id,
        timeout=30,  # seconds
    ))


def get_kafka_client(client_id=GENERIC_KAFKA_CLIENT_ID):
    return KafkaClient(
        bootstrap_servers=settings.KAFKA_BROKERS,
        client_id=client_id,
        api_version=settings.KAFKA_API_VERSION
    )
