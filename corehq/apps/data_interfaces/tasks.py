import uuid

from celery.task import task
from celery.utils.log import get_task_logger
from django.core.cache import cache
from django.template.loader import render_to_string
from soil import CachedDownload

from corehq.apps.data_interfaces.utils import add_cases_to_case_group, archive_forms
from dimagi.utils.django.email import send_HTML_email

logger = get_task_logger('data_interfaces')
ONE_HOUR = 60 * 60

@task
def bulk_upload_cases_to_group(download_id, domain, case_group_id, cases):
    results = add_cases_to_case_group(domain, case_group_id, cases)
    temp_id = uuid.uuid4().hex
    cache.set(download_id, results, ONE_HOUR)

@task
def bulk_archive_forms(user, uploaded_data):
    response = archive_forms(user, uploaded_data)
    [logger.info("[Data interfaces] {}".format(msg)) for msg in response['errors']]
    [logger.info("[Data interfaces] {}".format(msg)) for msg in response['success']]

    html_content = render_to_string('data_interfaces/archive_email.html', response)
    send_HTML_email('Your archived forms', user.email, html_content)




