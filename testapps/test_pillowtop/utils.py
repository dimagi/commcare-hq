import uuid
from kafka import KafkaConsumer
from kafka.common import KafkaUnavailableError

from corehq.util.decorators import ContextDecorator
from corehq.util.test_utils import trap_extra_setup
from nose.tools import nottest
from pillowtop import get_pillow_by_name
from django.conf import settings

@nottest
def get_test_kafka_consumer(topic):
    """
    Gets a KafkaConsumer object for the topic, or conditionally raises
    a skip error for the test if Kafka is not available
    """
    with trap_extra_setup(KafkaUnavailableError):
        return KafkaConsumer(
            topic,
            group_id='test-{}'.format(uuid.uuid4().hex),
            bootstrap_servers=[settings.KAFKA_URL],
            consumer_timeout_ms=100,
        )


def get_current_kafka_seq(topic):
    consumer = get_test_kafka_consumer(topic)
    return consumer.offsets()['fetch'].get((topic, 0), 0)


class process_kafka_changes(ContextDecorator):
    def __init__(self, pillow_name, topic):
        self.topic = topic
        with real_pillow_settings():
            self.pillow = get_pillow_by_name(pillow_name, instantiate=True)

    def __enter__(self):
        self.kafka_seq = get_current_kafka_seq(self.topic)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.pillow.process_changes(since=self.kafka_seq, forever=False)


class real_pillow_settings(ContextDecorator):
    def __enter__(self):
        self._PILLOWTOPS = settings.PILLOWTOPS
        if not settings.PILLOWTOPS:
            # assumes HqTestSuiteRunner, which blanks this out and saves a copy here
            settings.PILLOWTOPS = settings._PILLOWTOPS

    def __exit__(self, exc_type, exc_val, exc_tb):
        settings.PILLOWTOPS = self._PILLOWTOPS
