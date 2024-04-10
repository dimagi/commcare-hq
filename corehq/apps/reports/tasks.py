import os
import uuid
import zipfile
from datetime import datetime, timedelta

from celery.schedules import crontab
from celery.utils.log import get_task_logger
from django.utils.translation import gettext as _
from django.http import HttpResponseRedirect, HttpRequest
from django.urls import reverse
from text_unidecode import unidecode

from casexml.apps.case.xform import extract_case_blocks
from couchforms.analytics import app_has_been_submitted_to_in_last_30_days
from dimagi.utils.chunked import chunked
from dimagi.utils.logging import notify_exception
from soil import DownloadBase
from soil.util import expose_blob_download

from corehq.apps.celery import periodic_task, task
from corehq.apps.domain.calculations import all_domain_stats, calced_props
from corehq.apps.domain.models import Domain
from corehq.apps.es import AppES, DomainES, FormES, filters
from corehq.apps.es.apps import app_adapter
from corehq.apps.es.domains import domain_adapter
from corehq.apps.export.const import MAX_MULTIMEDIA_EXPORT_SIZE
from corehq.apps.reports.models import QueryStringHash
from corehq.apps.reports.exceptions import FormArchiveError
from corehq.apps.reports.util import send_report_download_email
from corehq.blobs import CODES, get_blob_db
from corehq.const import ONE_DAY
from corehq.form_processor.models import CommCareCase, XFormInstance
from corehq.util.dates import get_timestamp_for_filename
from corehq.util.files import TransientTempfile, safe_filename_header
from corehq.util.metrics import metrics_gauge
from corehq.util.view_utils import absolute_reverse

from .analytics.esaccessors import (
    get_form_ids_having_multimedia,
    get_form_ids_with_multimedia,
    scroll_case_names,
)

logger = get_task_logger(__name__)
EXPIRE_TIME = ONE_DAY


@periodic_task(run_every=crontab(hour="22", minute="0", day_of_week="*"), queue='background_queue')
def update_calculated_properties():
    domains_to_update = DomainES().filter(
        get_domains_to_update_es_filter()
    ).fields(["name", "_id"]).run().hits

    for chunk in chunked(domains_to_update, 5000):
        update_calculated_properties_for_domains.delay(chunk)


@task(queue='background_queue')
def update_calculated_properties_for_domains(domains):
    """
    :param domains: list of {'name': <name>, '_id': <id>} entries
    """
    # relying on caching for efficiency
    all_stats = all_domain_stats()

    active_users_by_domain = {}
    for domain in domains:
        domain_obj = Domain.get_by_name(domain['name'])
        if not domain_obj:
            domain_adapter.delete(domain['_id'])
            continue
        try:
            props = calced_props(domain_obj, domain['_id'], all_stats)
            active_users_by_domain[domain['name']] = props['cp_n_active_cc_users']
            if props['cp_first_form'] is None:
                del props['cp_first_form']
            if props['cp_last_form'] is None:
                del props['cp_last_form']
            if props['cp_300th_form'] is None:
                del props['cp_300th_form']
            domain_adapter.update(domain['_id'], props)
        except Exception as e:
            notify_exception(
                None, message='Domain {} failed on stats calculations with {}'.format(domain['name'], e)
            )

    datadog_report_user_stats('commcare.active_mobile_workers.count', active_users_by_domain)


@periodic_task(run_every=timedelta(minutes=1), queue='background_queue')
def run_datadog_user_stats():
    all_stats = all_domain_stats()

    datadog_report_user_stats(
        'commcare.mobile_workers.count',
        commcare_users_by_domain=all_stats['commcare_users'],
    )


def datadog_report_user_stats(metric_name, commcare_users_by_domain):
    commcare_users_by_domain = summarize_user_counts(commcare_users_by_domain, n=50)
    for domain, user_count in commcare_users_by_domain.items():
        metrics_gauge(metric_name, user_count, tags={
            'domain': '_other' if domain == () else domain
        }, multiprocess_mode='max')


def summarize_user_counts(commcare_users_by_domain, n):
    """
    Reduce (domain => user_count) to n entries, with all other entries summed to a single one

    This allows us to report individual domain data to datadog for the domains that matter
    and report a single number that combines the users for all other domains.

    :param commcare_users_by_domain: the source data
    :param n: number of domains to reduce the map to
    :return: (domain => user_count) of top domains
             with a single entry under () for all other domains
    """
    user_counts = sorted((user_count, domain) for domain, user_count in commcare_users_by_domain.items())
    if n:
        top_domains, other_domains = user_counts[-n:], user_counts[:-n]
    else:
        top_domains, other_domains = [], user_counts[:]
    other_entry = (sum(user_count for user_count, _ in other_domains), ())
    return {domain: user_count for user_count, domain in top_domains + [other_entry]}


def get_domains_to_update_es_filter():
    """
    Returns ES filter to obtain domains that are active, and meet one or more
    of the following criteria:
     - never had calculated properties updated
     - calculated properties was updated over one week ago
     - new form submissions within the last day
    """
    last_week = datetime.utcnow() - timedelta(days=7)
    more_than_a_week_ago = filters.date_range('cp_last_updated', lt=last_week)
    not_updated = filters.missing('cp_last_updated')
    domains_submitted_today = (FormES().submitted(gte=datetime.utcnow() - timedelta(days=1))
        .terms_aggregation('domain.exact', 'domain').size(0).run().aggregations.domain.keys)
    is_domain_active = filters.term('is_active', True)
    return filters.AND(
        is_domain_active,
        filters.OR(
            not_updated,
            more_than_a_week_ago,
            filters.term('name', domains_submitted_today)
        )
    )


def is_app_active(app_id, domain):
    return app_has_been_submitted_to_in_last_30_days(domain, app_id)


@periodic_task(run_every=crontab(hour="2", minute="0", day_of_week="*"), queue='background_queue')
def apps_update_calculated_properties():
    query = AppES().is_build(False).values_list('_id', 'domain', scroll=True)
    for doc_id, domain in query:
        doc = {
            "cp_is_active": is_app_active(doc_id, domain),
        }
        app_adapter.update(doc_id, doc)


@task(serializer='pickle', ignore_result=True)
def export_all_rows_task(ReportClass, report_state, recipient_list=None, subject=None):
    report = object.__new__(ReportClass)
    report.__setstate__(report_state)
    report.rendered_as = 'export'

    setattr(report.request, 'REQUEST', {})
    file = report.excel_response
    report_class = report.__class__.__module__ + '.' + report.__class__.__name__

    # Some HQ-wide reports (e.g. accounting/smsbillables) will not have a domain associated with them
    # This uses the user's first domain to store the file in the blobdb
    report_storage_domain = report.request.couch_user.get_domains()[0] if report.domain is None else report.domain

    hash_id = _store_excel_in_blobdb(report_class, file, report_storage_domain, report.slug)
    logger.info(f'Stored report {report.name} with parameters: {report_state["request_params"]} in hash {hash_id}')
    if not recipient_list:
        recipient_list = [report.request.couch_user.get_email()]
    for recipient in recipient_list:
        link = absolute_reverse("export_report", args=[report_storage_domain, str(hash_id), report.export_format])
        _send_email(report, link, recipient=recipient, subject=subject)
        logger.info(f'Sent {report.name} with hash {hash_id} to {recipient}')


def _send_email(report, link, recipient, subject=None):
    send_report_download_email(report.name, recipient, link, subject, domain=report.domain)


def _store_excel_in_blobdb(report_class, file, domain, report_slug):
    key = uuid.uuid4().hex
    expired = 60 * 24 * 7  # 7 days
    db = get_blob_db()

    kw = {
        "domain": domain,
        "name": f"{report_slug}-{get_timestamp_for_filename()}",
        "parent_id": key,
        "type_code": CODES.tempfile,
        "key": key,
        "timeout": expired,
        "properties": {"report_class": report_class}
    }
    file.seek(0)
    db.put(file, **kw)
    return key


@task(serializer='pickle')
def build_form_multimedia_zipfile(
        domain,
        export_id,
        es_filters,
        download_id,
        owner_id,
):
    from corehq.apps.export.export import get_export_query
    from corehq.apps.export.models import FormExportInstance
    export = FormExportInstance.get(export_id)
    es_query = get_export_query(export, es_filters)
    form_ids = get_form_ids_with_multimedia(es_query)
    _generate_form_multimedia_zipfile(domain, export, form_ids, download_id, owner_id,
                                      build_form_multimedia_zipfile)


# ToDo: Remove post build_form_multimedia_zipfile rollout
@task(serializer='pickle')
def build_form_multimedia_zip(
        domain,
        export_id,
        datespan,
        user_types,
        download_id,
        owner_id,
):
    from corehq.apps.export.models import FormExportInstance
    export = FormExportInstance.get(export_id)
    form_ids = get_form_ids_having_multimedia(
        domain, export.app_id, export.xmlns, datespan, user_types
    )
    _generate_form_multimedia_zipfile(domain, export, form_ids, download_id, owner_id, build_form_multimedia_zip)


def _generate_form_multimedia_zipfile(domain, export, form_ids, download_id, owner_id, task_name):
    forms_info = _get_form_attachment_info(domain, form_ids, export)

    num_forms = len(forms_info)
    DownloadBase.set_progress(task_name, 0, num_forms)

    all_case_ids = set.union(*(info['case_ids'] for info in forms_info)) if forms_info else set()
    case_id_to_name = _get_case_names(domain, all_case_ids)

    with TransientTempfile() as temp_path:
        _write_attachments_to_file(temp_path, num_forms, forms_info, case_id_to_name)
        with open(temp_path, 'rb') as f:
            zip_name = 'multimedia-{}'.format(unidecode(export.name))
            _save_and_expose_zip(f, zip_name, domain, download_id, owner_id)

    DownloadBase.set_progress(task_name, num_forms, num_forms)


def _get_form_attachment_info(domain, form_ids, export):
    properties = _get_export_properties(export)
    return [
        _extract_form_attachment_info(form, properties)
        for form in XFormInstance.objects.iter_forms(form_ids, domain)
    ]


def _get_case_names(domain, case_ids):
    case_id_to_name = {c: c for c in case_ids}
    for case in scroll_case_names(domain, case_ids):
        if case.get('name'):
            case_id_to_name[case.get('_id')] = case.get('name')
    return case_id_to_name


def _format_filename(form_info, question_id, extension, case_id_to_name):
    filename = "{}-{}-form_{}{}".format(
        unidecode(question_id),
        form_info['username'] or form_info['form'].user_id or 'user_unknown',
        form_info['form'].form_id or 'unknown',
        extension
    )
    if form_info['case_ids']:
        case_names = '-'.join(map(
            lambda case_id: case_id_to_name[case_id],
            form_info['case_ids'],
        ))
        filename = '{}-{}'.format(case_names, filename)
    return filename


def _write_attachments_to_file(fpath, num_forms, forms_info, case_id_to_name):
    total_size = 0
    unique_attachment_ids = set()
    unique_names = {}
    with zipfile.ZipFile(fpath, 'w') as multimedia_zipfile:
        for form_number, form_info in enumerate(forms_info, 1):
            form = form_info['form']
            for attachment in form_info['attachments']:
                if attachment['id'] in unique_attachment_ids:
                    continue

                unique_attachment_ids.add(attachment['id'])
                total_size += attachment['size']
                if total_size >= MAX_MULTIMEDIA_EXPORT_SIZE:
                    raise Exception("Refusing to make multimedia export bigger than {} GB"
                                    .format(MAX_MULTIMEDIA_EXPORT_SIZE / 1024**3))
                filename = _format_filename(
                    form_info,
                    attachment['question_id'],
                    attachment['extension'],
                    case_id_to_name
                )
                filename = _make_unique_filename(filename, unique_names)
                zip_info = zipfile.ZipInfo(filename, attachment['timestamp'])
                multimedia_zipfile.writestr(zip_info, form.get_attachment(
                    attachment['name']),
                    zipfile.ZIP_STORED
                )
            DownloadBase.set_progress(build_form_multimedia_zip, form_number, num_forms)


def _make_unique_filename(filename, unique_names):
    while filename in unique_names:
        unique_names[filename] += 1
        root, ext = os.path.splitext(filename)
        filename = f"{root}-{unique_names[filename]}{ext}"
    unique_names[filename] = 1
    return filename


def _save_and_expose_zip(f, zip_name, domain, download_id, owner_id):
    expiry_minutes = 60
    get_blob_db().put(
        f,
        key=download_id,
        domain=domain,
        parent_id=domain,
        type_code=CODES.form_multimedia,
        timeout=expiry_minutes,
    )
    expose_blob_download(
        download_id,
        expiry=expiry_minutes * 60,  # seconds
        mimetype='application/zip',
        content_disposition=safe_filename_header(zip_name, 'zip'),
        download_id=download_id,
        owner_ids=[owner_id],
    )


def _convert_legacy_indices_to_export_properties(indices):
    # Strip the prefixed 'form' and change '.'s to '-'s
    return set(map(
        lambda index: '-'.join(index.split('.')[1:]),
        # Filter out any columns that are not form questions
        list(filter(
            lambda index: index and index.startswith('form'),
            indices,
        )),
    ))


def _get_export_properties(export):
    """
    Return a list of strings corresponding to form questions that are
    included in the export.
    """
    properties = set()
    for table in export.tables:
        for column in table.columns:
            if column.selected and column.item:
                path_parts = [n.name for n in column.item.path]
                path_parts = path_parts[1:] if path_parts[0] == "form" else path_parts
                properties.add("-".join(path_parts))
    return properties


def _get_question_id_for_attachment(form, attachment_name):
    """
    Attempts to build and return a question_id from retrieved path list
    """
    question_id_components = _find_path_to_question_id(form, attachment_name, use_basename=False)

    # NOTE: until rd-toolkit bug is fixed, search for question_id again looking at basename of attachment_name
    # See https://dimagi-dev.atlassian.net/browse/SAAS-11792
    if question_id_components is None:
        question_id_components = _find_path_to_question_id(form, attachment_name, use_basename=True)

    if question_id_components is not None:
        return str('-'.join(question_id_components))
    else:
        return None


def _find_path_to_question_id(form, attachment_name, use_basename=False):
    """
    Returns the list of keys used to find attachment_name in the form (None if not found)
    use_basename only applies to values that are an absolute path
    """
    if not isinstance(form, dict):
        # Recursive calls should always give `form` a form value.
        # However, https://dimagi-dev.atlassian.net/browse/SAAS-11326
        # was caused by resized repeats, where empty string tokens were
        # inserted rather than no element.
        # This check can be removed when repeats handle resizing.
        return None

    for k, v in form.items():
        if isinstance(v, dict):
            ret = _find_path_to_question_id(v, attachment_name, use_basename=use_basename)
            if ret:
                return [k] + ret
        elif isinstance(v, list):
            for repeat in v:
                ret = _find_path_to_question_id(repeat, attachment_name, use_basename=use_basename)
                if ret:
                    return [k] + ret
        else:
            if use_basename and os.path.isabs(v):
                # only worth using basename if path is absolute since that is the edge case this attempts to solve
                v = os.path.basename(v)
            if v == attachment_name:
                return [k]

    return None


def _extract_form_attachment_info(form, properties):
    """
    This is a helper function for build_form_multimedia_zip.
    Return a dict containing information about the given form and its relevant
    attachments
    """

    unknown_number = 0

    case_blocks = extract_case_blocks(form.form_data)
    form_info = {
        'form': form,
        'attachments': [],
        'case_ids': {c['@case_id'] for c in case_blocks},
        'username': form.get_data('form/meta/username')
    }

    for attachment_name, attachment in form.attachments.items():
        content_type = attachment.content_type
        if content_type == 'text/xml':
            continue

        question_id = _get_question_id_for_attachment(form.form_data, attachment_name)
        if question_id is None:
            question_id = 'unknown' + str(unknown_number)
            unknown_number += 1

        if not properties or question_id in properties:
            extension = str(os.path.splitext(attachment_name)[1])
            form_info['attachments'].append({
                'id': attachment.id,
                'size': attachment.content_length,
                'name': attachment_name,
                'question_id': question_id,
                'extension': extension,
                'timestamp': form.received_on.timetuple(),
            })

    return form_info


@periodic_task(run_every=crontab(minute=0, hour=1, day_of_week='sun'), queue='background_queue')
def delete_old_query_hash():
    query_hashes = QueryStringHash.objects.filter(last_accessed__lte=datetime.utcnow() - timedelta(days=365))
    for query in query_hashes:
        query.delete()


@task(serializer='pickle', queue='background_queue')
def _soft_delete_cases_and_forms(request, domain, case_delete_list, form_delete_list,
                                 redirect_url=None, main_case_name=None):
    from corehq.apps.reports.views import archive_form, unarchive_form

    if isinstance(request, dict):
        new_request = HttpRequest()
        for key, value in request.items():
            setattr(new_request, key, value)
        request = new_request
    error = False
    # msg = _("{}, its related subcases and submission forms were deleted successfully.").format(main_case_name)
    archived_forms = []

    def archive_forms(form_list):
        for form in form_list:
            if not archive_form(request, domain, form, is_case_delete=True):
                raise FormArchiveError(form)
            archived_forms.append(form)

    try:
        archive_forms(form_delete_list)
    except FormArchiveError:
        # Try sorting all forms first
        form_obj_list = XFormInstance.objects.get_forms(
            [form for form in form_delete_list if form not in archived_forms]
        )
        sorted_form_delete_list = sorted(form_obj_list, key=lambda form: form.received_on, reverse=True)
        try:
            archive_forms([form.form_id for form in sorted_form_delete_list])
        except FormArchiveError as e:
            # I'm fairly certain this will never enter here but this is just in case something does go wrong
            for form in archived_forms:
                unarchive_form(request, domain, form, is_case_delete=True)
            # msg = _("The form {} could not be deleted. Please try manually archiving, then deleting the form, "
            #         "before trying to delete this case again.").format(e)
            error = True

    if not error and [form.is_archived for form in XFormInstance.objects.get_forms(form_delete_list)]:
        XFormInstance.objects.soft_delete_forms(domain, list(form_delete_list))
        CommCareCase.objects.soft_delete_cases(domain, list(case_delete_list))

    # To eventually re-use after implementing progress bar
    """
    default_redirect = HttpResponseRedirect(reverse('project_report_dispatcher', args=(domain, 'submit_history')))
    
    if error:
        messages.error(request, msg, extra_tags='html')
        if not redirect_url:
            return default_redirect
        return HttpResponseRedirect(redirect_url)
    else:
        messages.success(request, msg)
        return default_redirect
        """
