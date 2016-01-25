import json
import time

from corehq.util.soft_assert import soft_assert
from kafka.common import LeaderNotAvailableError, FailedPayloadsError


def send_to_kafka(producer, topic, change_meta):
    def _send_to_kafka():
        producer.send_messages(
            bytes(topic),
            bytes(change_meta.domain.encode('utf-8') if change_meta.domain is not None else None),
            bytes(json.dumps(change_meta.to_json())),
        )

    try:
        try:
            _send_to_kafka()
        except FailedPayloadsError:
            # this typically an inactivity timeout - which can happen if the feed is low volume
            # just do a simple retry
            _send_to_kafka()
    except LeaderNotAvailableError:
        # kafka seems to be down. sleep a bit to avoid crazy amounts of error spam
        time.sleep(15)
        raise
    except Exception as e:
        _assert = soft_assert(to='@'.join(['czue', 'dimagi.com']))
        _assert(False, u'Problem sending change to kafka {}: {} ({})'.format(
            change_meta.to_json(), e, type(e)
        ))
        raise
