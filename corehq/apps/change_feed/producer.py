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
KAFKA_AUDIT_LOGGER = 'kafka_producer_audit'
MAX_PRODUCER_RETRIES = 3

logger = logging.getLogger(KAFKA_AUDIT_LOGGER)


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
        if settings.USE_KAFKA_SHORTEST_BACKLOG_PARTITIONER:
            from corehq.apps.change_feed.partitioners import choose_best_partition_for_topic
            partition = choose_best_partition_for_topic(topic)
        else:
            partition = None

        message = change_meta.to_json()
        message_json_dump = json.dumps(message).encode('utf-8')
        change_meta._transaction_id = uuid.uuid4().hex
        try:
            _audit_log(CHANGE_PRE_SEND, change_meta)
            future = self.producer.send(topic, message_json_dump, key=change_meta.document_id, partition=partition)
            if self.auto_flush:
                future.get()
                _audit_log(CHANGE_SENT, change_meta)
        except Exception as e:
            _audit_log('ERROR', change_meta)
            raise KafkaPublishingError(e)

        if not self.auto_flush:
            on_success = partial(_on_success, change_meta)
            on_error = partial(_on_error, topic, change_meta)
            future.add_callback(on_success).add_errback(on_error)

    def flush(self, timeout=None):
        self.producer.flush(timeout=timeout)


def _on_success(change_meta, record_metadata):
    _audit_log(CHANGE_SENT, change_meta)


def _on_error(topic, change_meta, exc_info):
    _audit_log(CHANGE_ERROR, change_meta)
    meta_json = change_meta.to_json()
    meta_json['producer_retries'] = change_meta.producer_retry_count
    notify_exception(
        None, 'Problem sending change to Kafka (async)',
        details=meta_json, exec_info=exc_info
    )
    if change_meta.producer_retry_count <= MAX_PRODUCER_RETRIES:
        change_meta.add_retry()
        producer.send_change(topic, change_meta)


def _audit_log(stage, change_meta):
    logger.debug(
        '%s,%s,%s,%s', stage,
        change_meta.document_type, change_meta.document_id, change_meta._transaction_id
    )


producer = ChangeProducer()
