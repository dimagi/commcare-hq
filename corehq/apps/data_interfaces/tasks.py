from celery.task import task
from celery.utils.log import get_task_logger
from django.core.cache import cache
from django.template.loader import render_to_string
from django.utils.translation import ugettext as _

from corehq.apps.data_interfaces.utils import add_cases_to_case_group, archive_forms_old, archive_or_restore_forms
from .interfaces import FormManagementMode
from corehq.elastic import es_query
from corehq.pillows.mappings.xform_mapping import XFORM_INDEX
from dimagi.utils.django.email import send_HTML_email

logger = get_task_logger('data_interfaces')
ONE_HOUR = 60 * 60


@task(ignore_result=True)
def bulk_upload_cases_to_group(download_id, domain, case_group_id, cases):
    results = add_cases_to_case_group(domain, case_group_id, cases)
    cache.set(download_id, results, ONE_HOUR)


@task(ignore_result=True)
def bulk_archive_forms(domain, user, uploaded_data):
    # archive using Excel-data
    response = archive_forms_old(domain, user, uploaded_data)

    for msg in response['success']:
        logger.info("[Data interfaces] %s", msg)
    for msg in response['errors']:
        logger.info("[Data interfaces] %s", msg)

    html_content = render_to_string('data_interfaces/archive_email.html', response)
    send_HTML_email(_('Your archived forms'), user.email, html_content)


@task
def bulk_form_management_async(archive_or_restore, domain, user, es_dict_or_formids):
    # bulk archive/restore
    # es_dict_or_formids - can either be list of formids or a partial es-query dict that returns
    def get_form_ids(es_query_dict, domain):
        query = es_query(
            params={'domain.exact': domain},
            q=es_query_dict,
            es_url=XFORM_INDEX + '/xform/_search',
        )
        form_ids = [res['_id'] for res in query.get('hits', {}).get('hits', [])]
        return form_ids

    task = bulk_form_management_async
    mode = FormManagementMode(archive_or_restore, validate=True)

    if type(es_dict_or_formids) == list:
        xform_ids = es_dict_or_formids
    elif type(es_dict_or_formids) == dict:
        xform_ids = get_form_ids(es_dict_or_formids, domain)
    response = archive_or_restore_forms(domain, user, xform_ids, mode, task)
    return response
