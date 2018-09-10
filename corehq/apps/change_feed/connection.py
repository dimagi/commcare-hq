from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf import settings
from kafka import KafkaClient
from kafka.common import KafkaUnavailableError
import logging


def get_kafka_client(client_id="general-cchq-kafka"):
    # configure connections_max_idle_ms?
    return KafkaClient(
        bootstrap_servers=settings.KAFKA_BROKERS,
        config_id=client_id,
        request_timeout_ms=100,
        api_version=(0, 8, 2),
    )


def get_kafka_client_or_none():
    try:
        return get_kafka_client()
    except KafkaUnavailableError:
        logging.warning('Ignoring missing kafka client during unit testing')
        return None
