from celery.task import task
from dimagi.utils.couch.undo import DELETED_SUFFIX
from django.core.cache import cache
import uuid
from soil import CachedDownload, DownloadBase


@task
def bulk_upload_async(domain, user_specs, group_specs, location_specs):
    from corehq.apps.users.bulkupload import create_or_update_users_and_groups
    task = bulk_upload_async
    DownloadBase.set_progress(task, 0, 100)
    results = create_or_update_users_and_groups(
        domain,
        user_specs,
        group_specs,
        location_specs,
        task=task,
    )
    DownloadBase.set_progress(task, 100, 100)
    return {
        'messages': results
    }

@task(rate_limit=2, queue='doc_deletion_queue')  # limit this to two bulk saves a second so cloudant has time to reindex
def tag_docs_as_deleted(cls, docs, deletion_id):
    for doc in docs:
        doc['doc_type'] += DELETED_SUFFIX
        doc['-deletion_id'] = deletion_id
    cls.get_db().bulk_save(docs)
