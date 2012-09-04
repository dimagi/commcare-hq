from celery.task import task
from django.core.cache import cache
import uuid
from soil import CachedDownload
from corehq.apps.users.bulkupload import create_or_update_users_and_groups

@task
def bulk_upload_async(download_id, domain, user_specs, group_specs):
    results = create_or_update_users_and_groups(domain, user_specs, group_specs)
    temp_id = uuid.uuid4().hex
    expiry = 60*60
    cache.set(temp_id, results, expiry)
    cache.set(download_id, CachedDownload(temp_id,content_disposition="", 
                                          mimetype="text/html"), expiry)
    