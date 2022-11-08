import json
import logging
import uuid
from functools import partial

from django.conf import settings

from kafka import KafkaProducer

from corehq.form_processor.exceptions import KafkaPublishingError
from dimagi.utils.logging import notify_exception

CHANGE_PRE_SEND = 'PRE-SEND'
CHANGE_ERROR = 'ERROR'
CHANGE_SENT = 'SENT'


class ChangeProducer(object):

    def __init__(self, auto_flush=True):
        self.auto_flush = auto_flush
        self._producer = None

    @property
    def producer(self):
        if self._producer is not None:
            return self._producer

        self._producer = KafkaProducer(
            bootstrap_servers=settings.KAFKA_BROKERS,
            api_version=settings.KAFKA_API_VERSION,
            client_id="cchq-producer",
            retries=3,
            acks=1,
            key_serializer=lambda key: str(key).encode()
        )
        return self._producer

    def send_change(self, topic, change_meta):
        message = change_meta.to_json()
        message_json_dump = json.dumps(message).encode('utf-8')
        change_meta._transaction_id = uuid.uuid4().hex
        try:
            future = self.producer.send(topic, message_json_dump, key=change_meta.document_id)
            if self.auto_flush:
                future.get()
        except Exception as e:
            raise KafkaPublishingError(e)

        if not self.auto_flush:
            on_error = partial(_on_error, change_meta)
            future.add_errback(on_error)

    def flush(self, timeout=None):
        self.producer.flush(timeout=timeout)


def _on_error(change_meta, exc_info):
    notify_exception(
        None, 'Problem sending change to Kafka (async)',
        details=change_meta.to_json(), exec_info=exc_info
    )


producer = ChangeProducer()
