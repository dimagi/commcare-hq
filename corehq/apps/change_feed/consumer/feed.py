import json
from django.conf import settings
from kafka import KafkaConsumer
from corehq.apps.change_feed.models import ChangeMeta
from pillowtop.feed.interface import ChangeFeed, Change


class KafkaChangeFeed(ChangeFeed):
    """
    Kafka-based implementation of a ChangeFeed
    """

    def __init__(self, topic):
        self._topic = topic

    def iter_changes(self, since, forever):
        consumer = _get_consumer(self._topic)
        partition = 0  # todo: does this need to be configurable?
        offset = int(since)  # coerce sequence IDs to ints
        # this is how you tell the consumer to start from a certion point in the sequence
        consumer.set_topic_partitions((self._topic, partition, offset))
        for message in consumer:
            yield change_from_kafka_message(message)


def _get_consumer(topic):
    return KafkaConsumer(
        topic,
        group_id='test-consumer',  # todo: what belongs here?
        bootstrap_servers=[settings.KAFKA_URL],
        consumer_timeout_ms=100,  # todo: what belongs here?
    )


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
