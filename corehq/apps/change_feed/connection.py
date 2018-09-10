from __future__ import absolute_import
from __future__ import unicode_literals

import logging

from django.conf import settings
from kafka.client import SimpleClient
from kafka.client import KafkaClient
from kafka.common import KafkaUnavailableError


GENERIC_KAFKA_CLIENT_ID = 'cchq-kafka-client'


def get_simple_kafka_client(client_id=GENERIC_KAFKA_CLIENT_ID):
    return SimpleClient(
        hosts=settings.KAFKA_BROKERS,
        client_id=client_id,
        timeout=30,  # seconds
    )


def get_simple_kafka_client_or_none(client_id=GENERIC_KAFKA_CLIENT_ID):
    try:
        return get_simple_kafka_client(client_id)
    except KafkaUnavailableError:
        logging.warning('Ignoring missing kafka client during unit testing')
        return None


def get_kafka_client(client_id=GENERIC_KAFKA_CLIENT_ID):
    return KafkaClient(
        bootstrap_servers=settings.KAFKA_BROKERS,
        client_id=client_id
    )
