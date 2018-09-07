from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf import settings
from kafka import KafkaClient
from kafka.common import KafkaUnavailableError
import logging


_kafka_client = None


def get_kafka_client():
    global _kafka_client
    if _kafka_client is None:
        _kafka_client = KafkaClient(settings.KAFKA_BROKERS)
    return _kafka_client


def get_kafka_client_or_none():
    try:
        return get_kafka_client()
    except KafkaUnavailableError:
        logging.warning('Ignoring missing kafka client during unit testing')
        return None
