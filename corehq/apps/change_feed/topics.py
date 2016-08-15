from kafka.common import OffsetRequest

from corehq.apps.change_feed.connection import get_kafka_client
from corehq.apps.change_feed.exceptions import UnavailableKafkaOffset
from .document_types import CASE, FORM, DOMAIN, META, APP

# this is redundant but helps avoid import warnings until nothing references these
CASE = CASE
FORM = FORM
DOMAIN = DOMAIN
META = META
APP = APP

# new models
CASE_SQL = 'case-sql'
FORM_SQL = 'form-sql'
SMS = 'sms'
LEDGER = 'ledger'
COMMCARE_USER = 'commcare-user'
GROUP = 'group'
WEB_USER = 'web-user'


ALL = (
    CASE,
    CASE_SQL,
    COMMCARE_USER,
    DOMAIN,
    FORM,
    FORM_SQL,
    GROUP,
    LEDGER,
    META,
    SMS,
    WEB_USER,
    APP,
)


def get_topic(document_type_object):
    return document_type_object.primary_type


def get_topic_offset(topic):
    """
    :returns: The kafka offset for the topic."""
    return get_multi_topic_offset([topic])[topic]


def get_all_offsets():
    """
    :returns: A dict of offsets keyed by topic"""
    return get_multi_topic_offset(ALL)


def get_multi_topic_offset(topics):
    """
    :returns: A dict of offsets keyed by topic"""
    return _get_topic_offsets(topics, latest=True)


def get_multi_topic_first_available_offsets(topics):
    """
    :returns: A dict of offsets keyed by topic"""
    return _get_topic_offsets(topics, latest=False)


def _get_topic_offsets(topics, latest):
    # https://cwiki.apache.org/confluence/display/KAFKA/A+Guide+To+The+Kafka+Protocol#AGuideToTheKafkaProtocol-OffsetRequest
    time_value = -1 if latest else -2
    assert set(topics) <= set(ALL)
    client = get_kafka_client()
    offset_requests = [OffsetRequest(topic, 0, time_value, 1) for topic in topics]
    responses = client.send_offset_request(offset_requests)
    return {
        r.topic: r.offsets[0] for r in responses
    }


def validate_offsets(expected_offsets):
    """
    Takes in a dictionary of offsets (topics to checkpoint numbers) and ensures they are all available
    in the current kafka feed
    """
    if expected_offsets:
        available_offsets = get_multi_topic_first_available_offsets([str(x) for x in expected_offsets.keys()])
        for topic in expected_offsets.keys():
            if expected_offsets[topic] < available_offsets[topic]:
                messsage = (
                    'First available topic offset for {} is {} but needed {}.'
                ).format(topic, available_offsets[topic], expected_offsets[topic])
                raise UnavailableKafkaOffset(messsage)
