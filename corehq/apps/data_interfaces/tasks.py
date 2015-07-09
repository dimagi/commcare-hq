import uuid

from celery.task import task
from celery.utils.log import get_task_logger
from django.core.cache import cache
from django.template.loader import render_to_string
from soil import CachedDownload, DownloadBase
from django.utils.translation import ugettext as _

from corehq.apps.data_interfaces.utils import add_cases_to_case_group, archive_forms_old, archive_or_restore_forms
from dimagi.utils.django.email import send_HTML_email

logger = get_task_logger('data_interfaces')
ONE_HOUR = 60 * 60


@task(ignore_result=True)
def bulk_upload_cases_to_group(download_id, domain, case_group_id, cases):
    results = add_cases_to_case_group(domain, case_group_id, cases)
    cache.set(download_id, results, ONE_HOUR)


@task(ignore_result=True)
def bulk_archive_forms(domain, user, uploaded_data):
    response = archive_forms_old(domain, user, uploaded_data)

    for msg in response['success']:
        logger.info("[Data interfaces] %s", msg)
    for msg in response['errors']:
        logger.info("[Data interfaces] %s", msg)

    html_content = render_to_string('data_interfaces/archive_email.html', response)
    send_HTML_email(_('Your archived forms'), user.email, html_content)


@task
def bulk_form_management_async(archive_or_restore, domain, user, xform_ids):
    # ToDo refactor archive_or_restore
    task = bulk_form_management_async
    if archive_or_restore:
        message = "Archive Forms"
        mode = "archive"
    else:
        message = "Restore Forms"
        mode = "restore"

    print "setting 0"
    DownloadBase.set_progress(task, 0, 100)
    print "set to 0"

    print "yeah we returned this"
    response = archive_or_restore_forms(domain, user, xform_ids, mode)
    print response
    DownloadBase.set_progress(task, 100, 100)
    return {'messages': {'errors': ['done done']}}

    for msg_type in ('success', 'error'):
        for msg in response[msg_type]:
            logger.info("[Data interfaces][{manage_mode}] {msg}".format(manage_mode=message, msg=msg))
