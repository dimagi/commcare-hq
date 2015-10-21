import json
from django.conf import settings
from kafka import KafkaConsumer
from kafka.common import ConsumerTimeout
from corehq.apps.change_feed.models import ChangeMeta
from pillowtop.feed.interface import ChangeFeed, Change


class KafkaChangeFeed(ChangeFeed):
    """
    Kafka-based implementation of a ChangeFeed
    """

    def __init__(self, topic):
        self._topic = topic

    def iter_changes(self, since, forever):
        # in milliseconds, -1 means wait forever for changes
        timeout = -1 if forever else 100
        consumer = KafkaConsumer(
            self._topic,
            group_id='test-consumer',  # todo: what belongs here?
            bootstrap_servers=[settings.KAFKA_URL],
            consumer_timeout_ms=timeout,
        )

        partition = 0  # todo: does this need to be configurable?
        offset = int(since)  # coerce sequence IDs to ints
        # this is how you tell the consumer to start from a certain point in the sequence
        consumer.set_topic_partitions((self._topic, partition, offset))
        for message in consumer:
            try:
                yield change_from_kafka_message(message)
            except ConsumerTimeout:
                assert not forever, 'Kafka pillow should not timeout when waiting forever!'
                # no need to do anything since this is just telling us we've reached the end of the feed


def change_from_kafka_message(message):
    change_meta = change_meta_from_kafka_message(message.value)
    return Change(
        id=change_meta.document_id,
        sequence_id=None,
        document=None,
        deleted=change_meta.is_deletion,
        metadata=change_meta,
    )


def change_meta_from_kafka_message(message):
    return ChangeMeta.wrap(json.loads(message))
