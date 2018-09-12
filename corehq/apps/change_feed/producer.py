from __future__ import unicode_literals
from __future__ import absolute_import
import json
import time

from corehq.util.soft_assert import soft_assert
from kafka import SimpleProducer
from kafka.common import LeaderNotAvailableError, FailedPayloadsError, KafkaUnavailableError
from corehq.apps.change_feed.connection import get_simple_kafka_client
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

    def __init__(self):
        self._kafka = None
        self._producer = None
        self._has_error = False

    @property
    def kafka(self):
        if self._kafka is None:
            self._kafka = get_simple_kafka_client(client_id='cchq-producer')
        return self._kafka

    @property
    def producer(self):
        if self._producer is not None:
            return self._producer

        self._producer = SimpleProducer(
            self.kafka, async_send=False, req_acks=SimpleProducer.ACK_AFTER_LOCAL_WRITE,
            sync_fail_on_error=True
        )
        return self._producer

    def send_change(self, topic, change_meta):
        if self.producer:
            send_to_kafka(self.producer, topic, change_meta)


producer = ChangeProducer()
