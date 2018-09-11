from __future__ import unicode_literals
from __future__ import absolute_import
import json
import time
from django.conf import settings

from corehq.util.soft_assert import soft_assert
from kafka import SimpleProducer
from kafka.common import LeaderNotAvailableError, FailedPayloadsError, KafkaUnavailableError
from corehq.apps.change_feed.connection import get_kafka_client_or_none
from six.moves import range


def send_to_kafka(producer, topic, change_meta):
    def _send_to_kafka():
        producer.send_messages(
            bytes(topic),
            bytes(json.dumps(change_meta.to_json())),
        )

    try:
        tries = 3
        for i in range(tries):
            # try a few times because the python kafka libraries can trigger timeouts
            # if they are idle for a while.
            try:
                _send_to_kafka()
                break
            except (FailedPayloadsError, KafkaUnavailableError, LeaderNotAvailableError):
                if i == (tries - 1):
                    # if it's the last try, fail hard
                    raise
    except LeaderNotAvailableError:
        # kafka seems to be down. sleep a bit to avoid crazy amounts of error spam
        time.sleep(15)
        raise
    except Exception as e:
        _assert = soft_assert(notify_admins=True)
        _assert(False, 'Problem sending change to kafka {}: {} ({})'.format(
            change_meta.to_json(), e, type(e)
        ))
        raise


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
                _assert = soft_assert(notify_admins=True)
                _assert(settings.DEBUG, 'Kafka is not available! Change producer is doing nothing.')
                self._has_error = True
        return self._kafka

    @property
    def producer(self):
        if self._producer is None and not self._has_error:
            if self.kafka is not None:
                self._producer = SimpleProducer(self._kafka)
            else:
                # if self.kafka is None then we should be in an error state
                assert self._has_error
        return self._producer

    def send_change(self, topic, change_meta):
        if self.producer:
            send_to_kafka(self.producer, topic, change_meta)


producer = ChangeProducer()
