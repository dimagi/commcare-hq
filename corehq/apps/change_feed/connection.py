from django.conf import settings

from corehq.util.io import ClosingContextProxy
from kafka import KafkaClient, KafkaConsumer

GENERIC_KAFKA_CLIENT_ID = 'cchq-kafka-client'


def get_kafka_client(client_id=GENERIC_KAFKA_CLIENT_ID):
    return ClosingContextProxy(KafkaClient(
        bootstrap_servers=settings.KAFKA_BROKERS,
        client_id=client_id,
        api_version=settings.KAFKA_API_VERSION
    ))


def get_kafka_consumer():
    return ClosingContextProxy(KafkaConsumer(
        client_id='pillowtop_utils',
        bootstrap_servers=settings.KAFKA_BROKERS,
    ))
