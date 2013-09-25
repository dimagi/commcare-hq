import uuid
from celery.task import task
from django.core.cache import cache
from corehq.apps.data_interfaces.utils import add_cases_to_case_group
from soil import CachedDownload


@task
def bulk_upload_cases_to_group(download_id, domain, case_group_id, cases):
    results = add_cases_to_case_group(domain, case_group_id, cases)
    temp_id = uuid.uuid4().hex
    expiry = 60 * 60
    cache.set(download_id, results, expiry)
