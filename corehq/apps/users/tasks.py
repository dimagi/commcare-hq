from celery.task import task
from dimagi.utils.couch.undo import DELETED_SUFFIX
from django.core.cache import cache
import uuid
from soil import CachedDownload

@task
def bulk_upload_async(download_id, domain, user_specs, group_specs, location_specs):
    from corehq.apps.users.bulkupload import create_or_update_users_and_groups
    results = create_or_update_users_and_groups(
        domain,
        user_specs,
        group_specs,
        location_specs
    )
    temp_id = uuid.uuid4().hex
    expiry = 60*60
    cache.set(temp_id, results, expiry)
    cache.set(download_id, CachedDownload(temp_id, content_disposition="",
                                          mimetype="text/html"), expiry)

@task(rate_limit=2, queue='doc_deletion_queue')  # limit this to two bulk saves a second so cloudant has time to reindex
def tag_docs_as_deleted(cls, docs, deletion_id):
    for doc in docs:
        doc['doc_type'] += DELETED_SUFFIX
        doc['-deletion_id'] = deletion_id
    cls.get_db().bulk_save(docs)
