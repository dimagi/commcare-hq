from django.conf import settings
from kafka import KafkaConsumer
from kafka.partitioner.hashed import murmur2
from memoized import memoized

from corehq.apps.change_feed import topics
from corehq.util.quickcache import quickcache
from dimagi.utils.logging import notify_exception
from pillowtop import get_pillow_by_name, get_all_pillow_configs


TOPIC_TO_PILLOW_NAME_MAP = {
    topics.CASE: 'case-pillow',
    topics.CASE_SQL: 'case-pillow',
    topics.FORM: 'xform-pillow',
    topics.FORM_SQL: 'xform-pillow',
}


def choose_best_partition_for_topic(topic, key, shuffle_shards_per_key=5):
    """
    Choose the best partition for topic through shuffle-sharding

    - Map each key onto :shuffle_shards_per_key: partitions using consistent hashing
    - Within those, pick the partition with the shortest backlog

    Shuffle-sharding (as proponents put it) has the almost magical effect of simulating
    one queue per key, isolating customers to a large extent from each others' workloads.

    A :key: value of None is assigned to all partitions, and is thus a way of disabling
    shuffle-sharding and going for the shortest of all partitions.

    If :shuffle_shards_per_key: or is greater than the number of partitions
    then the key is irrelevant and all keys are assigned to all partitions;
    this has the same effect as using key=None.

    For more on shuffle-sharding see:
    https://aws.amazon.com/blogs/architecture/shuffle-sharding-massive-and-magical-fault-isolation/
    """
    if topic not in _get_topic_to_pillow_map():
        # None means there's no best, use the default
        return None

    backlog_lengths_by_partition = _get_backlog_lengths_by_partition(topic)
    all_partitions = set(backlog_lengths_by_partition.keys())
    if not key:
        whitelist = all_partitions
    else:
        # map key to the partitions it's assigned to
        whitelist = _n_choose_k_hash(
            key=key,
            n=max(all_partitions) + 1,
            k=shuffle_shards_per_key,
        ) & all_partitions

    _, best_partition = min(
        (backlog_length, partition)
        for partition, backlog_length in backlog_lengths_by_partition.items()
        if partition in whitelist
    )
    return best_partition


@quickcache(['topic'], memoize_timeout=10, timeout=10)
def _get_backlog_lengths_by_partition(topic):
    """Return partition => backlog_length map where partition and backlog length are ints"""
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


def _n_choose_k_hash(key, n, k):
    """
    Hash key to a set of k unique numbers from 0 to n-1 inclusive and return the set

    Given the same arguments the function will return the same thing every time,
    but for any given key it return a random-looking set of k unique numbers in range(n).
    """
    choices = set()
    seed = key
    while len(choices) < n and len(choices) < k:
        seed = murmur2(f'{key}{seed}'.encode('utf-8'))
        choices.add(seed % n)
    return choices
