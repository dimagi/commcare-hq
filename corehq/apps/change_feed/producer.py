from __future__ import unicode_literals
from __future__ import absolute_import
import json
import six

from django.conf import settings
from kafka import KafkaProducer

from corehq.util.soft_assert import soft_assert


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
        message_json_dump = json.dumps(message)
        if six.PY3:
            message_json_dump = message_json_dump.encode('utf-8')
        try:
            self.producer.send(topic, message_json_dump, key=change_meta.document_id)
            if self.auto_flush:
                self.producer.flush()
        except Exception as e:
            _assert = soft_assert(notify_admins=True)
            _assert(False, 'Problem sending change to kafka {}: {} ({})'.format(
                message, e, type(e)
            ))
            raise

    def flush(self, timeout=None):
        self.producer.flush(timeout=timeout)


producer = ChangeProducer()
