from kafka import TopicPartition

from corehq.apps.app_manager.util import app_doc_types
from corehq.apps.change_feed.connection import get_kafka_consumer
from corehq.apps.change_feed.exceptions import UnavailableKafkaOffset
from corehq.form_processor.models import XFormInstance

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


CASE_TOPICS = (CASE_SQL, )
FORM_TOPICS = (FORM_SQL, )
USER_TOPICS = (COMMCARE_USER, WEB_USER)
ALL = (
    CASE_SQL,
    COMMCARE_USER,
    DOMAIN,
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
        return CASE_SQL
    elif doc_type in XFormInstance.ALL_DOC_TYPES:
        return FORM_SQL
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
    assert set(topics) <= set(ALL)
    with get_kafka_consumer() as consumer:
        get_offsets = consumer.end_offsets if latest else consumer.beginning_offsets
        return get_offsets([
            TopicPartition(topic, partition)
            for topic in topics
            for partition in consumer.partitions_for_topic(topic)
        ])


def get_all_kafka_partitons_for_topic(topic):
    """
    :returns: A set of strings containing topic and the partition numbers for the given topic.
    For example:
    {'form-sql-0', 'form-sql-1', 'form-sql-2'}
    """
    paritions_and_offsets = _get_topic_offsets([topic], latest=False)
    return set(f"{topic}-{offset}" for (topic, offset) in paritions_and_offsets.keys())


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
