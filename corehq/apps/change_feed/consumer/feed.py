import json
from dimagi.utils.logging import notify_error
from django.conf import settings
from kafka import KafkaConsumer
from kafka.common import ConsumerTimeout, KafkaConfigurationError, KafkaUnavailableError
from corehq.apps.change_feed.data_sources import get_document_store
from corehq.apps.change_feed.exceptions import UnknownDocumentStore
import logging
from pillowtop.feed.interface import ChangeFeed, Change, ChangeMeta


MIN_TIMEOUT = 100


class KafkaChangeFeed(ChangeFeed):
    """
    Kafka-based implementation of a ChangeFeed
    """

    def __init__(self, topics, group_id, partition=0):
        """
        Create a change feed listener for a list of kafka topics, a group ID, and partition.

        See http://kafka.apache.org/documentation.html#introduction for a description of what these are.
        """
        self._topics = topics
        self._group_id = group_id
        self._partition = partition

    def __unicode__(self):
        return u'KafkaChangeFeed: topics: {}, group: {}'.format(self._topics, self._group_id)

    def _get_single_topic_or_fail(self):
        if len(self._topics != 1):
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

        reset = 'smallest' if since is not None else 'largest'
        consumer = self._get_consumer(timeout, auto_offset_reset=reset)
        if since is not None:
            if isinstance(since, dict):
                # multiple topics
                offsets = [(topic, self._partition, offset) for topic, offset in since.items()]
            else:
                # single topic
                topic = self._get_single_topic_or_fail()
                try:
                    offset = int(since)  # coerce sequence IDs to ints
                except ValueError:
                    notify_error("kafka pillow {} couldn't parse sequence ID {}. rewinding...".format(
                        self._group_id, since
                    ))
                    # since kafka only keeps 7 days of data this isn't a big deal. Hopefully we will only see
                    # these once when each pillow moves over.
                    offset = 0
                offsets = [(topic, self._partition, offset)]

            # this is how you tell the consumer to start from a certain point in the sequence
            consumer.set_topic_partitions(*offsets)
        try:
            for message in consumer:
                yield change_from_kafka_message(message)
        except ConsumerTimeout:
            assert not forever, 'Kafka pillow should not timeout when waiting forever!'
            # no need to do anything since this is just telling us we've reached the end of the feed

    def get_current_offsets(self):
        consumer = self._get_consumer(MIN_TIMEOUT, auto_offset_reset='smallest')
        try:
            # we have to fetch the changes to populate the highwater offsets
            # todo: there is likely a cleaner way to do this
            changes = list(consumer)
        except ConsumerTimeout:
            pass
        except (KafkaConfigurationError, KafkaUnavailableError) as e:
            # kafka seems to be having issues. log it and move on
            logging.exception(u'Problem getting latest offsets form kafka for {}: {}'.format(
                self,
                e,
            ))
            return None

        highwater_offsets = consumer.offsets('highwater')
        return {
            topic: highwater_offsets[(topic, self._partition)]
            for topic in self._topics
        }

    def get_latest_change_id(self):
        topic = self._get_single_topic_or_fail()
        return self.get_current_offsets()[topic]

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
