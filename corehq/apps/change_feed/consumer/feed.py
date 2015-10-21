import json
from corehq.apps.change_feed.models import ChangeMeta
from pillowtop.feed.interface import ChangeFeed, Change


class KafkaChangeFeed(ChangeFeed):
    """
    Kafka-based implementation of a ChangeFeed
    """

    def __init__(self, kafka_consumer):
        self._kafka_consumer = kafka_consumer

    def iter_changes(self, since, forever):
        # todo: honor since and forever args
        for message in self._kafka_consumer:
            yield change_from_kafka_message(message)


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
