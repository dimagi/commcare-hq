from __future__ import unicode_literals
from __future__ import absolute_import
import json
import time
from django.conf import settings

from corehq.util.soft_assert import soft_assert
from kafka import KafkaProducer
from kafka.common import LeaderNotAvailableError, FailedPayloadsError, KafkaUnavailableError
from six.moves import range


def send_to_kafka(producer, topic, change_meta):
    def _send_to_kafka():
        producer.send(
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
                producer.flush()
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
        self._producer = None
        self._has_error = False

    @property
    def producer(self):
        if self._producer is None:
            self._producer = KafkaProducer(
                bootstrap_servers=settings.KAFKA_BROKERS,
                client_id='change-producer',
                acks='all', retries=1
            )
        return self._producer

    def send_change(self, topic, change_meta):
        if self.producer:
            send_to_kafka(self.producer, topic, change_meta)


producer = ChangeProducer()
