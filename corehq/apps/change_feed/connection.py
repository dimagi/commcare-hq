from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf import settings
from kafka import KafkaClient
from kafka.common import KafkaUnavailableError
import logging


def get_kafka_client():
    # todo: we may want to make this more configurable
    return KafkaClient(settings.KAFKA_URL)


def get_kafka_client_or_none():
    try:
        return get_kafka_client()
    except KafkaUnavailableError:
        logging.warning('Ignoring missing kafka client during unit testing')
        return None
