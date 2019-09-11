from datetime import timedelta, datetime
from time import sleep

from django.core.management import BaseCommand
from django.db.models import F
from django.db.models import Q

from corehq.form_processor.tasks import reprocess_submission
from corehq.util.datadog.gauges import datadog_gauge
from couchforms.models import UnfinishedSubmissionStub
from dimagi.utils.logging import notify_exception

ENQUEUING_TIMEOUT = 14 * 24 * 60    # 14 days (in minutes)

BATCH_SIZE = 1000


def _record_datadog_metrics():
    count = UnfinishedSubmissionStub.objects.count()
    datadog_gauge('commcare.submission_reprocessing.queue_size', count)


class SubmissionReprocessingEnqueuingOperation(BaseCommand):
    help = "Runs the Submission Reprocessing Queue"

    def handle(self, **options):
        while True:
            try:
                num_processed = self.create_tasks()
            except Exception:
                num_processed = 0
                notify_exception(None, message="Could not queue unprocessed submissions")
            sleep_time = 10 if num_processed < BATCH_SIZE else 0
            sleep(sleep_time)

    def create_tasks(self):
        stub_ids = self.get_items_to_be_processed()
        for stub_id in stub_ids:
            reprocess_submission.delay(stub_id)
        return len(stub_ids)

    def get_items_to_be_processed(self):
        _record_datadog_metrics()
        utcnow = datetime.utcnow()
        queued_threshold = utcnow - timedelta(minutes=ENQUEUING_TIMEOUT)
        min_processing_age = utcnow - timedelta(minutes=5)
        filters = Q(date_queued__isnull=True) | Q(date_queued__lte=queued_threshold)

        # wait 5 mins before processing to avoid processing during form submission
        filters = Q(timestamp__lt=min_processing_age) & filters
        query = UnfinishedSubmissionStub.objects.filter(filters).order_by('timestamp')
        stub_ids = list(query.values_list('id', flat=True)[:BATCH_SIZE])
        if stub_ids:
            UnfinishedSubmissionStub.objects.filter(pk__in=stub_ids).update(
                date_queued=utcnow, attempts=F('attempts') + 1
            )
        return stub_ids


class Command(SubmissionReprocessingEnqueuingOperation):
    pass
