import uuid
from django.conf import settings
from kafka import KafkaConsumer
from kafka.common import KafkaUnavailableError
from kafka.structs import TopicPartition
from nose.tools import nottest

from corehq.apps.change_feed.topics import get_topic_offset
from corehq.util.test_utils import trap_extra_setup


@nottest
def get_test_kafka_consumer(*topics):
    """
    Gets a KafkaConsumer object for the topic, or conditionally raises
    a skip error for the test if Kafka is not available
    """
    with trap_extra_setup(KafkaUnavailableError):
        configs = {
            'bootstrap_servers': [settings.KAFKA_URL],
            'consumer_timeout_ms': 100,
        }
        consumer = KafkaConsumer(**configs)
        consumer.assign([TopicPartition(topic, 0) for topic in topics])
        for topic in topics:
            consumer.position(TopicPartition(topic, 0))
        return consumer
