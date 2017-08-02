from corehq.form_processor.reprocess import reprocess_unfinished_stub
from corehq.util.celery_utils import no_result_task
from couchforms.models import UnfinishedSubmissionStub


SUBMISSION_REPROCESS_CELERY_QUEUE = 'submission_reprocessing_queue'


@no_result_task(queue=SUBMISSION_REPROCESS_CELERY_QUEUE, acks_late=True)
def reprocess_submission(submssion_stub_id):
    stub = UnfinishedSubmissionStub.objects.get(submssion_stub_id)
    reprocess_unfinished_stub(stub)
