from __future__ import absolute_import
from __future__ import unicode_literals

from datetime import datetime, timedelta

from celery.schedules import crontab
from celery.task import periodic_task

from casexml.apps.phone.const import SYNCLOG_RETENTION_DAYS
from couchforms.models import UnfinishedSubmissionStub
from dimagi.utils.couch import CriticalSection

from corehq.form_processor.models import CaseTransaction
from corehq.form_processor.reprocess import reprocess_unfinished_stub
from corehq.sql_db.util import get_db_aliases_for_partitioned_query
from corehq.util.celery_utils import no_result_task
from corehq.util.datadog.gauges import datadog_counter

SUBMISSION_REPROCESS_CELERY_QUEUE = 'submission_reprocessing_queue'


@no_result_task(serializer='pickle', queue=SUBMISSION_REPROCESS_CELERY_QUEUE, acks_late=True)
def reprocess_submission(submssion_stub_id):
    with CriticalSection(['reprocess_submission_%s' % submssion_stub_id]):
        try:
            stub = UnfinishedSubmissionStub.objects.get(id=submssion_stub_id)
        except UnfinishedSubmissionStub.DoesNotExist:
            return

        reprocess_unfinished_stub(stub)
        datadog_counter('commcare.submission_reprocessing.count')


@periodic_task(run_every=crontab(minute=0, hour='0,12'))
def null_old_synclogs_from_case_transactions():
    for dbname in get_db_aliases_for_partitioned_query():
        CaseTransaction.objects.using(dbname).filter(
            sync_log_id__isnull=False,
            server_date__lt=datetime.utcnow() - timedelta(days=SYNCLOG_RETENTION_DAYS),
        ).update(sync_log_id=None)
