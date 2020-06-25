import time
from datetime import timedelta

from celery.schedules import crontab
from celery.task import periodic_task
from django.conf import settings

from corehq.form_processor.reprocess import reprocess_unfinished_stub
from corehq.util.celery_utils import no_result_task
from corehq.util.decorators import serial_task
from corehq.util.metrics import metrics_counter, metrics_gauge
from couchforms.models import UnfinishedSubmissionStub
from dimagi.utils.couch import CriticalSection
from dimagi.utils.logging import notify_exception

SUBMISSION_REPROCESS_CELERY_QUEUE = 'submission_reprocessing_queue'


@no_result_task(serializer='pickle', queue=SUBMISSION_REPROCESS_CELERY_QUEUE, acks_late=True)
def reprocess_submission(submssion_stub_id):
    with CriticalSection(['reprocess_submission_%s' % submssion_stub_id]):
        try:
            stub = UnfinishedSubmissionStub.objects.get(id=submssion_stub_id)
        except UnfinishedSubmissionStub.DoesNotExist:
            return

        reprocess_unfinished_stub(stub)
        metrics_counter('commcare.submission_reprocessing.count')


@periodic_task(run_every=crontab(minute='*/5'), queue=settings.CELERY_PERIODIC_QUEUE)
def _reprocess_archive_stubs():
    reprocess_archive_stubs.delay()


@serial_task("reprocess_archive_stubs", queue=settings.CELERY_PERIODIC_QUEUE)
def reprocess_archive_stubs():
    # Check for archive stubs
    from corehq.form_processor.interfaces.dbaccessors import FormAccessors
    from couchforms.models import UnfinishedArchiveStub
    stubs = UnfinishedArchiveStub.objects.filter(attempts__lt=3)
    metrics_gauge('commcare.unfinished_archive_stubs', len(stubs), multiprocess_mode='max')
    start = time.time()
    cutoff = start + timedelta(minutes=4).total_seconds()
    for stub in stubs:
        # Exit this task after 4 minutes so that tasks remain short
        if time.time() > cutoff:
            return
        try:
            xform = FormAccessors(stub.domain).get_form(form_id=stub.xform_id)
            # If the history wasn't updated the first time around, run the whole thing again.
            if not stub.history_updated:
                FormAccessors.do_archive(xform, stub.archive, stub.user_id, trigger_signals=True)

            # If the history was updated the first time around, just send the update to kafka
            else:
                FormAccessors.publish_archive_action_to_kafka(xform, stub.user_id, stub.archive)
        except Exception:
            # Errors should not prevent processing other stubs
            notify_exception(None, "Error processing UnfinishedArchiveStub")
