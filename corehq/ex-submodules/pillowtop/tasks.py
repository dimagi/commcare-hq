from celery.schedules import crontab
from celery.task import periodic_task
from django.conf import settings

from corehq.util.datadog.gauges import datadog_counter, datadog_gauge, datadog_histogram
from corehq.util.decorators import serial_task
from pillowtop.utils import get_all_pillows_json


@periodic_task(run_every=crontab(minute="*/5"), queue=settings.CELERY_PERIODIC_QUEUE)
def run_pillow_datadog_metrics():
    pillow_datadog_metrics.delay()


@serial_task('pillow-datadog-metrics', timeout=30 * 60, queue=settings.CELERY_PERIODIC_QUEUE, max_retries=0)
def pillow_datadog_metrics():
    def _is_couch(pillow):
        # text is couch, json is kafka
        return pillow['seq_format'] == 'text'

    pillow_meta = get_all_pillows_json()

    for pillow in pillow_meta:
        tags = [
            'pillow_name:{}'.format(pillow['name']),
            'feed_type:{}'.format('couch' if _is_couch(pillow) else 'kafka')
        ]

        for topic_name, offset in pillow['offsets'].items():
            if _is_couch(pillow):
                assert isinstance(pillow['seq'], int)
                assert len(pillow['offsets']) == 1
                tags_with_topic = tags + ['topic:{}'.format(topic_name)]
                processed_offset = pillow['seq']
            else:
                assert isinstance(pillow['seq'], dict)
                if len(pillow['seq']) == 0:
                    # this pillow has never been initialized. 
                    # (custom pillows on most environments)
                    continue
                assert len(pillow['offsets']) == len(pillow['seq'])
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
