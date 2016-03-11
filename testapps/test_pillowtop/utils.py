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


def make_a_case(domain, case_id, case_name):
    # this avoids having to deal with all the reminders code bootstrap
    with drop_connected_signals(case_post_save):
        form, cases = post_case_blocks(
            [
                CaseBlock(
                    create=True,
                    case_id=case_id,
                    case_name=case_name,
                ).as_xml()
            ], domain=domain
        )
    return cases[0]
