from django.conf import settings
from kafka import KafkaConsumer, KafkaAdminClient, KafkaClient

from corehq.util.io import ClosingContextProxy

GENERIC_KAFKA_CLIENT_ID = 'cchq-kafka-client'


def get_kafka_client(client_id=GENERIC_KAFKA_CLIENT_ID):
    return KafkaClient(
        bootstrap_servers=settings.KAFKA_BROKERS,
        client_id=client_id,
        api_version=settings.KAFKA_API_VERSION
    )


def get_kafka_admin_client(client_id=GENERIC_KAFKA_CLIENT_ID) -> KafkaAdminClient:
    return ClosingContextProxy(KafkaAdminClient(
        bootstrap_servers=settings.KAFKA_BROKERS,
        client_id=client_id,
        api_version=settings.KAFKA_API_VERSION
    ))


def get_kafka_consumer() -> KafkaConsumer:
    return ClosingContextProxy(KafkaConsumer(
        client_id='pillowtop_utils',
        bootstrap_servers=settings.KAFKA_BROKERS,
        request_timeout_ms=1000
    ))
