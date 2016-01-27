import uuid
from kafka import KafkaConsumer
from kafka.common import KafkaUnavailableError
from corehq.util.test_utils import trap_extra_setup
import settings


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
