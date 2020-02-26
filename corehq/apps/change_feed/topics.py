from kafka import TopicPartition

from corehq.apps.app_manager.util import app_doc_types
from corehq.apps.change_feed.connection import get_kafka_consumer
from corehq.apps.change_feed.exceptions import UnavailableKafkaOffset
from couchforms.models import all_known_formlike_doc_types

CASE = 'case'
FORM = 'form'
DOMAIN = 'domain'
META = 'meta'
APP = 'app'
CASE_SQL = 'case-sql'
FORM_SQL = 'form-sql'
SMS = 'sms'
LEDGER = 'ledger'
COMMCARE_USER = 'commcare-user'
GROUP = 'group'
WEB_USER = 'web-user'
LOCATION = 'location'
SYNCLOG_SQL = 'synclog-sql'


CASE_TOPICS = (CASE, CASE_SQL)
FORM_TOPICS = (FORM, FORM_SQL)
USER_TOPICS = (COMMCARE_USER, WEB_USER)
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
    SYNCLOG_SQL,
)


def get_topic_for_doc_type(doc_type, data_source_type=None, default_topic=None):
    from corehq.apps.change_feed import document_types
    from corehq.apps.locations.document_store import LOCATION_DOC_TYPE

    if doc_type in document_types.CASE_DOC_TYPES:
        return {
            'sql': CASE_SQL,
            'couch': CASE
        }.get(data_source_type, CASE)
    elif doc_type in all_known_formlike_doc_types():
        return {
            'sql': FORM_SQL,
            'couch': FORM
        }.get(data_source_type, FORM)
    elif doc_type in document_types.DOMAIN_DOC_TYPES:
        return DOMAIN
    elif doc_type in document_types.MOBILE_USER_DOC_TYPES:
        return COMMCARE_USER
    elif doc_type in document_types.WEB_USER_DOC_TYPES:
        return WEB_USER
    elif doc_type in document_types.GROUP_DOC_TYPES:
        return GROUP
    elif doc_type in document_types.SYNCLOG_DOC_TYPES:
        return SYNCLOG_SQL
    elif doc_type in app_doc_types():
        return APP
    elif doc_type == LOCATION_DOC_TYPE:
        return LOCATION
    elif doc_type in ALL:  # for docs that don't have a doc_type we use the Kafka topic
        return doc_type
    elif default_topic:
        return default_topic
    else:
        # at some point we may want to make this more granular
        return META  # note this does not map to the 'meta' Couch database


def get_topic_offset(topic):
    """
    :returns: The kafka offset dict for the topic."""
    return get_multi_topic_offset([topic])


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
    :return: dict: { (topic, partition): offset, ... }
    """

    # https://cwiki.apache.org/confluence/display/KAFKA/A+Guide+To+The+Kafka+Protocol#AGuideToTheKafkaProtocol-OffsetRequest
    # https://cfchou.github.io/blog/2015/04/23/a-closer-look-at-kafka-offsetrequest/
    assert set(topics) <= set(ALL)
    with get_kafka_consumer() as consumer:
        offset_requests = []
        for topic in topics:
            partitions = consumer.partitions_for_topic(topic)
            for partition in partitions:
                offset_requests.append(TopicPartition(topic, partition))

        if latest:
            return consumer.end_offsets(offset_requests)
        else:
            return consumer.beginning_offsets(offset_requests)


def validate_offsets(expected_offsets):
    """
    Takes in a dictionary of offsets (topics to checkpoint numbers) and ensures they are all available
    in the current kafka feed
    """
    if expected_offsets:
        topics = {x[0] for x in expected_offsets.keys()}
        available_offsets = get_multi_topic_first_available_offsets(topics)
        for topic_partition, offset in expected_offsets.items():
            topic, partition = topic_partition
            if topic_partition not in available_offsets:
                raise UnavailableKafkaOffset("Invalid partition '{}' for topic '{}'".format(partition, topic))

            if expected_offsets[topic_partition] < available_offsets[topic_partition]:
                message = (
                    'First available topic offset for {}:{} is {} but needed {}.'
                ).format(topic, partition, available_offsets[topic_partition], expected_offsets[topic_partition])
                raise UnavailableKafkaOffset(message)
