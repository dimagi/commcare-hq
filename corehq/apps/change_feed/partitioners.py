from django.conf import settings
from kafka import KafkaConsumer
from memoized import memoized

from corehq.apps.change_feed import topics
from corehq.util.quickcache import quickcache
from dimagi.utils.logging import notify_exception
from pillowtop import get_pillow_by_name, get_all_pillow_configs


TOPIC_TO_PILLOW_NAME_MAP = {
    topics.CASE_SQL: 'case-pillow',
    topics.FORM_SQL: 'xform-pillow',
}


def choose_best_partition_for_topic(topic):
    if topic not in _get_topic_to_pillow_map():
        # None means there's no best, use the default
        return None

    try:
        backlog_lengths_by_partition = _get_backlog_lengths_by_partition(topic)
    except Exception:
        # if there's any issue whatsoever fetching offsets
        # fall back to the default partitioning algorithm
        notify_exception(None, "Error measuring kafka partition backlog lengths")
        return None
    else:
        _, best_partition = min(
            (backlog_length, partition)
            for partition, backlog_length in backlog_lengths_by_partition.items()
        )
        return best_partition


@quickcache(['topic'], memoize_timeout=10, timeout=10)
def _get_backlog_lengths_by_partition(topic):
    assert topic in _get_topic_to_pillow_map(), \
        f"Allowed topics are {', '.join(_get_topic_to_pillow_map().keys())}"

    pillow = _get_topic_to_pillow_map()[topic]
    seq_by_topic_partition = {
        topic_partition: seq
        for topic_partition, seq in pillow.get_checkpoint().wrapped_sequence.items()
        if topic_partition.topic == topic
    }
    backlog_length_by_partition = {}

    consumer = get_kafka_consumer_for_partitioning()
    offset_by_topic_partition = consumer.end_offsets(seq_by_topic_partition.keys())

    for key in set(seq_by_topic_partition) | set(offset_by_topic_partition):
        topic, partition = key
        backlog_length_by_partition[partition] = (
            offset_by_topic_partition[key] - seq_by_topic_partition[key])
    return backlog_length_by_partition


@memoized
def _get_topic_to_pillow_map():
    all_pillow_names = {config.name for config in get_all_pillow_configs()}
    return {
        topic: get_pillow_by_name(pillow_name)
        for topic, pillow_name in TOPIC_TO_PILLOW_NAME_MAP.items()
        if pillow_name in all_pillow_names
    }


@memoized
def get_kafka_consumer_for_partitioning():
    return KafkaConsumer(
        client_id='change_feed_partitioners',
        bootstrap_servers=settings.KAFKA_BROKERS,
    )
