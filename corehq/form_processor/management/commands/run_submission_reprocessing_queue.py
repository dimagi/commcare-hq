from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import timedelta, datetime

from django.conf import settings
from django.db.models import F
from django.db.models import Q

from corehq.util.datadog.gauges import datadog_gauge
from couchforms.models import UnfinishedSubmissionStub
from hqscripts.generic_queue import GenericEnqueuingOperation, QueueItem
from corehq.form_processor.tasks import reprocess_submission

ENQUEUING_TIMEOUT = 14 * 24 * 60    # 14 days (in minutes)


def _record_datadog_metrics():
    count = UnfinishedSubmissionStub.objects.count()
    datadog_gauge('commcare.submission_reprocessing.queue_size', count)


class SubmissionReprocessingEnqueuingOperation(GenericEnqueuingOperation):
    help = "Runs the Submission Reprocessing Queue"

    def get_queue_name(self):
        return "submission_reprocessing_queue"

    def get_enqueuing_timeout(self):
        return ENQUEUING_TIMEOUT

    def get_fetching_interval(self):
        return 5 * 60

    @classmethod
    def get_items_to_be_processed(cls, utcnow):
        _record_datadog_metrics()
        queued_threshold = utcnow - timedelta(minutes=ENQUEUING_TIMEOUT)
        min_processing_age = datetime.utcnow() - timedelta(minutes=5)
        filters = Q(date_queued__isnull=True) | Q(date_queued__lte=queued_threshold)

        # wait 5 mins before processing to avoid processing during form submission
        filters = Q(timestamp__lt=min_processing_age) & filters
        query = UnfinishedSubmissionStub.objects.filter(filters).order_by('timestamp')
        stub_ids = list(query.values_list('id', flat=True)[:1000])
        if stub_ids:
            UnfinishedSubmissionStub.objects.filter(pk__in=stub_ids).update(
                date_queued=utcnow, attempts=F('attempts') + 1
            )
        return [
            QueueItem(stub_id, '')
            for stub_id in stub_ids
        ]

    def use_queue(self):
        return settings.SUBMISSION_REPROCESSING_QUEUE_ENABLED

    def enqueue_item(self, item):
        reprocess_submission.delay(item.id)


class Command(SubmissionReprocessingEnqueuingOperation):
    pass
