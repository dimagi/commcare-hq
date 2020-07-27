from datetime import datetime
from time import sleep

from django.core.management import BaseCommand
from django.db import connection
from django.db.models import F

from couchforms.models import UnfinishedSubmissionStub
from dimagi.utils.logging import notify_exception

from corehq.form_processor.tasks import reprocess_submission
from corehq.util.metrics import metrics_gauge
from corehq.util.metrics.const import MPM_MAX

BATCH_SIZE = 1000


def _record_datadog_metrics():
    count = UnfinishedSubmissionStub.objects.count()
    metrics_gauge('commcare.submission_reprocessing.queue_size', count,
        multiprocess_mode=MPM_MAX)


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
        stub_ids = get_unfinished_stub_ids_to_process()
        if stub_ids:
            UnfinishedSubmissionStub.objects.filter(pk__in=stub_ids).update(
                date_queued=datetime.utcnow(), attempts=F('attempts') + 1
            )
        return stub_ids


def get_unfinished_stub_ids_to_process():
    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT id from {table} WHERE
            -- wait before processing to avoid processing during form submission
            -- and hopefully after any current infra issues
            timestamp < CURRENT_TIMESTAMP - interval '30 minutes'
            AND attempts <= 7  -- limit to 7 retries = 247 days old
            AND (
                date_queued IS NULL
                -- exponential back off. 3 and 7 chosen to make the back off steeper
                -- and also to give some jitter to the timing of when retries are attempted
                -- 7, 21, 63, 189, 567, 1701 hours (capped at 1701 ~= 71 days)
                OR date_queued < (CURRENT_TIMESTAMP - interval '7 hours' * power(3, LEAST(attempts, 5)))
            )
            ORDER BY timestamp
            LIMIT {batch_size}
            """.format(table=UnfinishedSubmissionStub._meta.db_table, batch_size=BATCH_SIZE),
        )
        return [row[0] for row in cursor.fetchall()]


class Command(SubmissionReprocessingEnqueuingOperation):
    pass
