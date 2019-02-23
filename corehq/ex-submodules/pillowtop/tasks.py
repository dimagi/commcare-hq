from __future__ import absolute_import
from __future__ import unicode_literals
from celery.schedules import crontab
from celery.task import periodic_task
from django.conf import settings

from corehq.util.datadog.gauges import datadog_gauge
from corehq.util.soft_assert import soft_assert
from pillowtop.utils import get_all_pillows_json


_assert = soft_assert("{}@{}".format('jemord', 'dimagi.com'))


@periodic_task(run_every=crontab(minute="*/2"), queue=settings.CELERY_PERIODIC_QUEUE)
def pillow_datadog_metrics():
    def _is_couch(pillow):
        # text is couch, json is kafka
        return pillow['seq_format'] == 'text'

    pillow_meta = get_all_pillows_json()

    active_pillows = getattr(settings, 'ACTIVE_PILLOW_NAMES', None)
    if active_pillows:
        pillow_meta = [pillow for pillow in pillow_meta if pillow['name'] in active_pillows]

    for pillow in pillow_meta:
        tags = [
            'pillow_name:{}'.format(pillow['name']),
            'feed_type:{}'.format('couch' if _is_couch(pillow) else 'kafka')
        ]

        datadog_gauge(
            'commcare.change_feed.seconds_since_last_update',
            pillow['seconds_since_last'], tags=tags
        )

        for topic_name, offset in pillow['offsets'].items():
            if _is_couch(pillow):
                if not isinstance(pillow['seq'], int) or len(pillow['offsets']) != 1:
                    _assert(False, "Unexpected couch pillow format {}".format(pillow['name']))
                    continue
                tags_with_topic = tags + ['topic:{}'.format(topic_name)]
                processed_offset = pillow['seq']
            else:
                if not pillow['seq']:
                    # this pillow has never been initialized.
                    # (custom pillows on most environments)
                    continue
                if not isinstance(pillow['seq'], dict) or len(pillow['offsets']) != len(pillow['seq']):
                    _assert(False, "Unexpected kafka pillow format {}".format(pillow['name']))
                    continue
                topic, partition = topic_name.split(',')
                tags_with_topic = tags + ['topic:{}-{}'.format(topic, partition)]
                processed_offset = pillow['seq'][topic_name]

            if processed_offset == 0:
                # assume if nothing has been processed that this pillow is not
                # supposed to be running
                continue

            datadog_gauge(
                'commcare.change_feed.current_offsets',
                offset, tags=tags_with_topic
            )
            datadog_gauge(
                'commcare.change_feed.processed_offsets',
                processed_offset, tags=tags_with_topic
            )
            needs_processing = offset - processed_offset
            datadog_gauge(
                'commcare.change_feed.need_processing',
                needs_processing, tags=tags_with_topic
            )
