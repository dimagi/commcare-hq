from __future__ import absolute_import
from __future__ import unicode_literals
import json
from copy import copy

from django.conf import settings
from kafka import KafkaConsumer
from kafka.common import ConsumerTimeout

from corehq.apps.change_feed.data_sources import get_document_store
from corehq.apps.change_feed.exceptions import UnknownDocumentStore
from corehq.apps.change_feed.topics import get_multi_topic_offset, validate_offsets
from memoized import memoized
from dimagi.utils.logging import notify_error
from pillowtop.checkpoints.manager import PillowCheckpointEventHandler
from pillowtop.models import kafka_seq_to_str
from pillowtop.feed.interface import ChangeFeed, Change, ChangeMeta
from six.moves import range

MIN_TIMEOUT = 100


class KafkaChangeFeed(ChangeFeed):
    """
    Kafka-based implementation of a ChangeFeed
    """
    sequence_format = 'json'

    def __init__(self, topics, group_id, strict=False, num_processes=1, process_num=0):
        """
        Create a change feed listener for a list of kafka topics, a group ID, and partition.

        See http://kafka.apache.org/documentation.html#introduction for a description of what these are.
        """
        self._topics = topics
        self._group_id = group_id
        self._processed_topic_offsets = {}
        self.strict = strict
        self.num_processes = num_processes
        self.process_num = process_num

    def __unicode__(self):
        return 'KafkaChangeFeed: topics: {}, group: {}'.format(self._topics, self._group_id)

    @property
    def topics(self):
        return self._topics

    @property
    @memoized
    def topic_and_partitions(self):
        return list(self._get_partitioned_offsets(get_multi_topic_offset(self.topics)))

    def _get_single_topic_or_fail(self):
        if len(self._topics) != 1:
            raise ValueError("This function requires a single topic but found {}!".format(self._topics))
        return self._topics[0]

    def iter_changes(self, since, forever):
        """
        Since must be a dictionary of topic partition offsets.
        """
        since = self._filter_offsets(since)
        # a special value of since=None will start from the end of the change stream
        if since is not None and (not isinstance(since, dict) or not since):
            raise ValueError("'since' must be None or a topic offset dictionary")

        # in milliseconds, -1 means wait forever for changes
        timeout = -1 if forever else MIN_TIMEOUT

        start_from_latest = since is None

        reset = 'largest' if start_from_latest else 'smallest'
        consumer = self._get_consumer(timeout, auto_offset_reset=reset)
        if not start_from_latest:
            if self.strict:
                validate_offsets(since)

            checkpoint_topics = {tp[0] for tp in since}
            extra_topics = checkpoint_topics - set(self._topics)
            if extra_topics:
                raise ValueError("'since' contains extra topics: {}".format(list(extra_topics)))

            self._processed_topic_offsets = copy(since)

            offsets = [
                copy(self._processed_topic_offsets)
            ]

            # this is how you tell the consumer to start from a certain point in the sequence
            consumer.set_topic_partitions(*offsets)

        try:
            for message in consumer:
                self._processed_topic_offsets[(message.topic, message.partition)] = message.offset
                yield change_from_kafka_message(message)
        except ConsumerTimeout:
            assert not forever, 'Kafka pillow should not timeout when waiting forever!'
            # no need to do anything since this is just telling us we've reached the end of the feed

    def get_current_checkpoint_offsets(self):
        # the way kafka works, the checkpoint should increment by 1 because
        # querying the feed is inclusive of the value passed in.
        latest_offsets = self.get_latest_offsets()
        ret = {}
        for topic_partition, sequence in self.get_processed_offsets().items():
            if sequence == latest_offsets[topic_partition]:
                # this topic and partition is totally up to date and if we add 1
                # then kafka will give us an offset out of range error.
                # not adding 1 to the partition means that we may process this
                # change again later, but that should be OK
                sequence = latest_offsets[topic_partition]
            else:
                sequence += 1
            ret[topic_partition] = sequence
        return self._filter_offsets(ret)

    def get_processed_offsets(self):
        return copy(self._processed_topic_offsets)

    def get_latest_offsets(self):
        return self._filter_offsets(get_multi_topic_offset(self.topics))

    def get_latest_offsets_json(self):
        return json.loads(kafka_seq_to_str(self.get_latest_offsets()))

    def get_latest_offsets_as_checkpoint_value(self):
        return self.get_latest_offsets()

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

    def _filter_offsets(self, offsets):
        if offsets is None:
            return offsets

        return {
            tp: offsets[tp]
            for tp in self.topic_and_partitions
            if tp in offsets
        }

    def _get_partitioned_offsets(self, offsets):
        topic_partitions = sorted(list(offsets))

        partitioned_topic_partitions = [
            topic_partitions[num::self.num_processes]
            for num in range(self.num_processes)
        ][self.process_num]

        return {
            tp: offset
            for tp, offset in offsets.items()
            if tp in partitioned_topic_partitions
        }


class KafkaCheckpointEventHandler(PillowCheckpointEventHandler):
    """
    Event handler that supports checkpoints when subscribing to multiple topics.
    """

    def __init__(self, checkpoint, checkpoint_frequency, change_feed, checkpoint_callback=None):
        super(KafkaCheckpointEventHandler, self).__init__(checkpoint, checkpoint_frequency, checkpoint_callback)
        assert isinstance(change_feed, KafkaChangeFeed)
        self.change_feed = change_feed

    def fire_change_processed(self, change, context):
        if self.should_update_checkpoint(context):
            updated_to = self.change_feed.get_current_checkpoint_offsets()
            self.update_checkpoint(updated_to)
            return True

        return False


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
        topic=message.topic,
    )


def change_meta_from_kafka_message(message):
    return ChangeMeta.wrap(json.loads(message))
