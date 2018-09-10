from __future__ import absolute_import
from __future__ import unicode_literals

import logging

from django.conf import settings
from kafka import KafkaClient
from kafka.common import KafkaUnavailableError


GENERIC_KAFKA_CLIENT_ID = 'cchq-kafka-client'


def get_kafka_client(client_id=GENERIC_KAFKA_CLIENT_ID):
    # configure connections_max_idle_ms?
    return KafkaClient(
        bootstrap_servers=settings.KAFKA_BROKERS,
        config_id=client_id,
        request_timeout_ms=100,
        api_version=settings.KAFKA_API_VERSION,
    )


def get_kafka_client_or_none(client_id=GENERIC_KAFKA_CLIENT_ID):
    try:
        return get_kafka_client(client_id)
    except KafkaUnavailableError:
        logging.warning('Ignoring missing kafka client during unit testing')
        return None
