import uuid
from kafka import KafkaConsumer
from kafka.common import KafkaUnavailableError
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.signals import case_post_save
from casexml.apps.case.util import post_case_blocks
from corehq.util.context_managers import drop_connected_signals
from corehq.util.test_utils import trap_extra_setup
from nose.tools import nottest
import settings


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
    # have to get the seq id before the change is processed
    return consumer.offsets()['fetch'][(topic, 0)]
