from django.conf import settings

from corehq.util.io import ClosingContextProxy
from kafka import KafkaClient, KafkaConsumer

GENERIC_KAFKA_CLIENT_ID = 'cchq-kafka-client'


def get_kafka_client(client_id=GENERIC_KAFKA_CLIENT_ID):
    return ClosingContextProxy(KafkaClient(
        bootstrap_servers=settings.KAFKA_BROKERS,
        client_id=client_id,
        api_version=get_kafka_api_version(),
    ))


def get_kafka_consumer():
    return ClosingContextProxy(KafkaConsumer(
        client_id='pillowtop_utils',
        bootstrap_servers=settings.KAFKA_BROKERS,
    ))


def get_kafka_api_version():
    ver = settings.KAFKA_API_VERSION
    return ver[:2] if ver else ver
