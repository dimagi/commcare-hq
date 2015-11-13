import json
from django.conf import settings
from kafka import KafkaConsumer
from kafka.common import ConsumerTimeout
from corehq.apps.change_feed.models import ChangeMeta
from pillowtop.feed.interface import ChangeFeed, Change


MIN_TIMEOUT = 100


class KafkaChangeFeed(ChangeFeed):
    """
    Kafka-based implementation of a ChangeFeed
    """

    def __init__(self, topic, group_id, partition=0):
        """
        Create a change feed listener for a particular kafka topic, group ID, and partition.

        See http://kafka.apache.org/documentation.html#introduction for a description of what these are.
        """
        self._topic = topic
        self._group_id = group_id
        self._partition = partition

    def iter_changes(self, since, forever):
        # in milliseconds, -1 means wait forever for changes
        timeout = -1 if forever else MIN_TIMEOUT

        consumer = self._get_consumer(timeout)
        offset = int(since)  # coerce sequence IDs to ints
        # this is how you tell the consumer to start from a certain point in the sequence
        consumer.set_topic_partitions((self._topic, self._partition, offset))
        for message in consumer:
            try:
                yield change_from_kafka_message(message)
            except ConsumerTimeout:
                assert not forever, 'Kafka pillow should not timeout when waiting forever!'
                # no need to do anything since this is just telling us we've reached the end of the feed

    def get_latest_change_id(self):
        consumer = self._get_consumer(MIN_TIMEOUT)
        # we have to fetch one change to populate the highwater offset
        consumer.next()
        return consumer.offsets('highwater')[(self._topic, self._partition)]

    def _get_consumer(self, timeout):
        return KafkaConsumer(
            self._topic,
            group_id=self._group_id,
            bootstrap_servers=[settings.KAFKA_URL],
            consumer_timeout_ms=timeout,
            auto_offset_reset='smallest',
        )


def change_from_kafka_message(message):
    change_meta = change_meta_from_kafka_message(message.value)
    return Change(
        id=change_meta.document_id,
        sequence_id=message.offset,
        document=None,
        deleted=change_meta.is_deletion,
        metadata=change_meta,
    )


def change_meta_from_kafka_message(message):
    return ChangeMeta.wrap(json.loads(message))
