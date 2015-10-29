from django.conf import settings
from kafka import KafkaClient


def get_kafka_client():
    # todo: we may want to make this more configurable
    return KafkaClient(settings.KAFKA_URL)
