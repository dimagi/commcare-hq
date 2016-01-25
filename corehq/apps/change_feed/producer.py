from kafka import KeyedProducer
from corehq.apps.change_feed.connection import get_kafka_client_or_none
import logging
from corehq.apps.change_feed.utils import send_to_kafka


class ChangeProducer(object):

    def __init__(self, kafka=None):
        self._kafka = kafka
        self._producer = None
        self._has_error = False

    @property
    def kafka(self):
        # load everything lazily to avoid doing this work if not needed
        if self._kafka is None and not self._has_error:
            self._kafka = get_kafka_client_or_none()
            if self._kafka is None:
                logging.warning('Kafka is not available! Change producer is doing nothing.')
                self._has_error = True
        return self._kafka

    @property
    def producer(self):
        if self._producer is None and not self._has_error:
            if self.kafka is not None:
                self._producer = KeyedProducer(self._kafka)
            else:
                # if self.kafka is None then we should be in an error state
                assert self._has_error
        return self._producer

    def send_change(self, topic, change_meta):
        if not self._has_error:
            send_to_kafka(self.producer, topic, change_meta)


producer = ChangeProducer()
