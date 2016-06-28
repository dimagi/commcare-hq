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
            'group_id': 'test-{}'.format(uuid.uuid4().hex),
            'bootstrap_servers': [settings.KAFKA_URL],
            'consumer_timeout_ms': 100,
        }
        return KafkaConsumer(*topics, **configs)


def get_current_kafka_seq(topic):
    consumer = get_test_kafka_consumer(topic)
    return consumer.offsets()['fetch'].get((topic, 0), 0)


def get_current_multi_topic_seq(topics):
    consumer = get_test_kafka_consumer(*topics)
    offsets = consumer.offsets('fetch')
    return {
        topic_part[0]: offset
        for topic_part, offset in offsets.items()
    }
