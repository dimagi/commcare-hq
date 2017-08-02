from datetime import timedelta

from django.conf import settings
from django.db.models import F
from django.db.models import Q

from couchforms.models import UnfinishedSubmissionStub
from hqscripts.generic_queue import GenericEnqueuingOperation
from corehq.form_processor.tasks import reprocess_submission


class SubmissionReprocessingEnqueuingOperation(GenericEnqueuingOperation):
    help = "Runs the Submission Reprocessing Queue"

    def get_queue_name(self):
        return "submission_reprocessing_queue"

    def get_enqueuing_timeout(self):
        return 30  # minutes

    @classmethod
    def get_items_to_be_processed(cls, utcnow):
        day_ago = utcnow - timedelta(days=1)
        queue_filter = Q(saved=False) & (Q(date_queued__isnull=True) | Q(date_queued__lte=day_ago))
        stub_ids = UnfinishedSubmissionStub.objects.filter(queue_filter).values_list('id', flat=True)[:1000]
        UnfinishedSubmissionStub.objects.filter(pk__in=stub_ids).update(
            date_queued=utcnow, attempts=F('attempts') + 1
        )
        return [
            {'id': stub_id, 'key': ''}
            for stub_id in stub_ids
        ]

    def use_queue(self):
        return settings.PILLOW_RETRY_QUEUE_ENABLED

    def enqueue_item(self, item_id):
        reprocess_submission.delay(item_id)


class Command(SubmissionReprocessingEnqueuingOperation):
    pass

