from corehq.apps.celery import task

from corehq.apps.data_cleaning.models import (
    BulkEditSession,
)


@task(queue='case_import_queue')
def commit_data_cleaning(bulk_edit_session_id):
    BulkEditSession.objects.get(session_id=bulk_edit_session_id)
