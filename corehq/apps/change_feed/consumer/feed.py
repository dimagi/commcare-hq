import json
from copy import copy

from django.conf import settings
from kafka import KafkaConsumer
from kafka.common import ConsumerTimeout

from corehq.apps.change_feed.data_sources import get_document_store
from corehq.apps.change_feed.exceptions import UnknownDocumentStore
from corehq.apps.change_feed.topics import get_multi_topic_offset, get_topic_offset, \
    validate_offsets
from dimagi.utils.logging import notify_error
from pillowtop.checkpoints.manager import PillowCheckpointEventHandler, DEFAULT_EMPTY_CHECKPOINT_SEQUENCE
from pillowtop.feed.interface import ChangeFeed, Change, ChangeMeta

MIN_TIMEOUT = 100


class KafkaChangeFeed(ChangeFeed):
    """
    Kafka-based implementation of a ChangeFeed
    """

    def __init__(self, topics, group_id, partition=0, strict=False):
        """
        Create a change feed listener for a list of kafka topics, a group ID, and partition.

        See http://kafka.apache.org/documentation.html#introduction for a description of what these are.
        """
        self._topics = topics
        self._group_id = group_id
        self._partition = partition
        self._processed_topic_offsets = {}  # maps topics to sequence IDs
        self.strict = strict

    def __unicode__(self):
        return u'KafkaChangeFeed: topics: {}, group: {}'.format(self._topics, self._group_id)

    @property
    def topics(self):
        return self._topics

    def _get_single_topic_or_fail(self):
        if len(self._topics) != 1:
            raise ValueError("This function requires a single topic but found {}!".format(self._topics))
        return self._topics[0]

    def iter_changes(self, since, forever):
        """
        Since can either be an integer (for single topic change feeds) or a dict
        of topics to integers (for multiple topic change feeds)
        """
        # a special value of since=None will start from the end of the change stream

        # in milliseconds, -1 means wait forever for changes
        timeout = -1 if forever else MIN_TIMEOUT

        start_from_latest = since is None

        reset = 'largest' if start_from_latest else 'smallest'
        consumer = self._get_consumer(timeout, auto_offset_reset=reset)
        if not start_from_latest:
            if isinstance(since, dict):
                if not since:
                    since = {topic: 0 for topic in self._topics}
                self._processed_topic_offsets = copy(since)
            else:
                # single topic
                single_topic = self._get_single_topic_or_fail()
                try:
                    offset = int(since)  # coerce sequence IDs to ints
                except ValueError:
                    notify_error("kafka pillow {} couldn't parse sequence ID {}. rewinding...".format(
                        self._group_id, since
                    ))
                    # since kafka only keeps 7 days of data this isn't a big deal. Hopefully we will only see
                    # these once when each pillow moves over.
                    offset = 0
                self._processed_topic_offsets = {single_topic: offset}

            def _make_offset_tuple(topic):
                if topic in self._processed_topic_offsets:
                    return (topic, self._partition, self._processed_topic_offsets[topic])
                else:
                    return (topic, self._partition)

            offsets = [_make_offset_tuple(topic) for topic in self._topics]
            if self.strict:
                self._validate_offsets(offsets)

            # this is how you tell the consumer to start from a certain point in the sequence
            consumer.set_topic_partitions(*offsets)

        try:
            for message in consumer:
                self._processed_topic_offsets[message.topic] = message.offset
                yield change_from_kafka_message(message)
        except ConsumerTimeout:
            assert not forever, 'Kafka pillow should not timeout when waiting forever!'
            # no need to do anything since this is just telling us we've reached the end of the feed

    def get_current_checkpoint_offsets(self):
        # the way kafka works, the checkpoint should increment by 1 because
        # querying the feed is inclusive of the value passed in.
        return {
            topic: sequence + 1 for topic, sequence in self._processed_topic_offsets.items()
        }

    def get_current_offsets(self):
        return get_multi_topic_offset(self.topics)

    def get_latest_change_id(self):
        topic = self._get_single_topic_or_fail()
        return get_topic_offset(topic)

    def get_checkpoint_value(self):
        try:
            return self.get_latest_change_id()
        except ValueError:
            return json.dumps(self.get_current_offsets())

    def _get_consumer(self, timeout, auto_offset_reset='smallest'):
        config = {
            'group_id': self._group_id,
            'bootstrap_servers': [settings.KAFKA_URL],
            'consumer_timeout_ms': timeout,
            'auto_offset_reset': auto_offset_reset,
        }
        return KafkaConsumer(
            *self._topics,
            **config
        )

    def _validate_offsets(self, offsets):
        expected_values = {offset[0]: offset[2] for offset in offsets if len(offset) > 2}
        validate_offsets(expected_values)


class MultiTopicCheckpointEventHandler(PillowCheckpointEventHandler):
    """
    Event handler that supports checkpoints when subscribing to multiple topics.
    """

    def __init__(self, checkpoint, checkpoint_frequency, change_feed):
        super(MultiTopicCheckpointEventHandler, self).__init__(checkpoint, checkpoint_frequency)
        assert isinstance(change_feed, KafkaChangeFeed)
        self.change_feed = change_feed
        # todo: do this somewhere smarter?
        checkpoint_doc = self.checkpoint.get_or_create_wrapped()
        if checkpoint_doc.sequence_format != 'json' or checkpoint_doc.sequence == DEFAULT_EMPTY_CHECKPOINT_SEQUENCE:
            checkpoint_doc.sequence_format = 'json'
            # convert initial default to json default
            if checkpoint_doc.sequence == DEFAULT_EMPTY_CHECKPOINT_SEQUENCE:
                checkpoint_doc.sequence = '{}'
            checkpoint_doc.save()

    def fire_change_processed(self, change, context):
        if context.changes_seen % self.checkpoint_frequency == 0 and context.do_set_checkpoint:
            updated_to = self.change_feed.get_current_checkpoint_offsets()
            self.checkpoint.update_to(json.dumps(updated_to))


def change_from_kafka_message(message):
    change_meta = change_meta_from_kafka_message(message.value)
    try:
        document_store = get_document_store(
            data_source_type=change_meta.data_source_type,
            data_source_name=change_meta.data_source_name,
            domain=change_meta.domain
        )
    except UnknownDocumentStore:
        document_store = None
        notify_error("Unknown document store: {}".format(change_meta.data_source_type))
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
