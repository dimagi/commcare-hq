from celery.schedules import crontab
from celery.task import periodic_task
from django.conf import settings

from corehq.util.datadog.gauges import datadog_gauge
from pillowtop.utils import get_all_pillows_json


@periodic_task(run_every=crontab(minute="*/2"), queue=settings.CELERY_PERIODIC_QUEUE)
def pillow_datadog_metrics():
    def _is_couch(pillow):
        # text is couch, json is kafka
        return pillow['seq_format'] == 'text'

    pillow_meta = get_all_pillows_json()
    for pillow in pillow_meta:
        # The host and group tags are added here to ensure they remain constant
        # regardless of which celery worker the task get's executed on.
        # Without this the sum of the metrics get's inflated.
        tags = [
            'pillow_name:{}'.format(pillow['name']),
            'feed_type:{}'.format('couch' if _is_couch(pillow) else 'kafka'),
            'host:celery',
            'group:celery'
        ]

        datadog_gauge(
            'commcare.change_feed.seconds_since_last_update',
            pillow['seconds_since_last'], tags=tags
        )

        for topic_name, offset in pillow['offsets'].items():
            if _is_couch(pillow):
                tags_with_topic = tags + ['topic:{}'.format(topic_name)]
                processed_offset = pillow['seq']
            else:
                if not pillow['seq']:
                    # this pillow has never been initialized.
                    # (custom pillows on most environments)
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
