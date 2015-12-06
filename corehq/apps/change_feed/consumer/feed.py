import json
from dimagi.utils.logging import notify_error
from django.conf import settings
from kafka import KafkaConsumer
from kafka.common import ConsumerTimeout
from corehq.apps.change_feed.data_sources import get_document_store
from corehq.apps.change_feed.exceptions import UnknownDocumentStore
from pillowtop.feed.interface import ChangeFeed, Change, ChangeMeta


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
        # a special value of since=None will start from the end of the change stream

        # in milliseconds, -1 means wait forever for changes
        timeout = -1 if forever else MIN_TIMEOUT

        reset = 'smallest' if since is not None else 'largest'
        consumer = self._get_consumer(timeout, auto_offset_reset=reset)
        if since is not None:
            try:
                offset = int(since)  # coerce sequence IDs to ints
            except ValueError:
                notify_error("kafka pillow {} couldn't parse sequence ID {}. rewinding...".format(
                    self._group_id, since
                ))
                # since kafka only keeps 7 days of data this isn't a big deal. Hopefully we will only see
                # these once when each pillow moves over.
                offset = 0
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

    def _get_consumer(self, timeout, auto_offset_reset='smallest'):
        return KafkaConsumer(
            self._topic,
            group_id=self._group_id,
            bootstrap_servers=[settings.KAFKA_URL],
            consumer_timeout_ms=timeout,
            auto_offset_reset=auto_offset_reset,
        )


def change_from_kafka_message(message):
    change_meta = change_meta_from_kafka_message(message.value)
    try:
        document_store = get_document_store(change_meta.data_source_type, change_meta.data_source_name)
    except UnknownDocumentStore:
        document_store = None
    return Change(
        id=change_meta.document_id,
        sequence_id=message.offset,
        document=None,
        deleted=change_meta.is_deletion,
        metadata=change_meta,
        document_store=document_store,
    )


def change_meta_from_kafka_message(message):
    return ChangeMeta.wrap(json.loads(message))
