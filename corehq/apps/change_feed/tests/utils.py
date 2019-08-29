import uuid

from django.conf import settings

from kafka import KafkaConsumer
from kafka.common import KafkaUnavailableError
from nose.tools import nottest

from corehq.util.test_utils import trap_extra_setup


@nottest
def get_test_kafka_consumer(*topics):
    """
    Gets a KafkaConsumer object for the topic, or conditionally raises
    a skip error for the test if Kafka is not available
    """
    with trap_extra_setup(KafkaUnavailableError):
        configs = {
            'bootstrap_servers': settings.KAFKA_BROKERS,
            'consumer_timeout_ms': 100,
            'enable_auto_commit': False,
        }
        consumer = KafkaConsumer(*topics, **configs)
        try:
            # initialize consumer
            next(consumer)
        except StopIteration:
            pass
        return consumer
