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
LOCATION = 'location'


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
    LOCATION,
)


def get_topic(document_type_object):
    return document_type_object.primary_type


def get_topic_offset(topic):
    """
    :returns: The kafka offset dict for the topic."""
    return get_multi_topic_offset([topic])


def get_all_offsets():
    """
    :returns: A dict of offsets keyed by topic and parition"""
    return get_multi_topic_offset(ALL)


def get_multi_topic_offset(topics):
    """
    :returns: A dict of offsets keyed by topic and partition"""
    return _get_topic_offsets(topics, latest=True)


def get_multi_topic_first_available_offsets(topics):
    """
    :returns: A dict of offsets keyed by topic and partition"""
    return _get_topic_offsets(topics, latest=False)


def _get_topic_offsets(topics, latest):
    """
    :param topics: list of topics
    :param latest: True to fetch latest offsets, False to fetch earliest available
    :return: {offset: {partition: offset}}
    """

    # https://cwiki.apache.org/confluence/display/KAFKA/A+Guide+To+The+Kafka+Protocol#AGuideToTheKafkaProtocol-OffsetRequest
    # https://cfchou.github.io/blog/2015/04/23/a-closer-look-at-kafka-offsetrequest/
    assert set(topics) <= set(ALL)
    client = get_kafka_client()
    partition_meta = client.topic_partitions

    # only return the offset of the latest message in the partition
    num_offsets = 1
    time_value = -1 if latest else -2

    offsets = {}
    offset_requests = []
    for topic in topics:
        partitions = list(partition_meta.get(topic, {}))
        offsets[topic] = {partition: None for partition in partitions}
        for partition in partitions:
            offset_requests.append(OffsetRequest(topic, partition, time_value, num_offsets))

    responses = client.send_offset_request(offset_requests)
    for r in responses:
        offsets[r.topic][r.partition] = r.offsets[0]

    return offsets


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
