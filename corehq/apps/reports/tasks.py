from __future__ import absolute_import
from __future__ import unicode_literals

import re
from datetime import datetime, timedelta
from dateutil.parser import parse
import hashlib
import os
import tempfile
from unidecode import unidecode
import uuid
import zipfile

from django.conf import settings

from celery.schedules import crontab
from celery.task import periodic_task
from celery.task import task
from celery.utils.log import get_task_logger

from casexml.apps.case.xform import extract_case_blocks
from corehq.apps.export.const import SAVED_EXPORTS_QUEUE
from corehq.apps.users.models import CouchUser
from corehq.util.log import send_HTML_email
from corehq.apps.reports.util import send_report_download_email
from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.util.dates import iso_string_to_datetime
from couchexport.files import Temp
from couchexport.groupexports import rebuild_export
from couchexport.tasks import cache_file_to_be_served
from couchforms.analytics import app_has_been_submitted_to_in_last_30_days
from dimagi.utils.couch.cache.cache_core import get_redis_client
from dimagi.utils.logging import notify_exception
from dimagi.utils.web import json_request
from django.http import HttpRequest
from django.utils.translation import ugettext as _

from soil import DownloadBase
from soil.util import expose_download

from corehq.apps.domain.calculations import (
    all_domain_stats,
    calced_props,
    CALC_FNS,
)
from corehq.apps.es.domains import DomainES
from corehq.elastic import (
    stream_es_query,
    send_to_elasticsearch,
    get_es_new, ES_META)
from corehq.pillows.mappings.app_mapping import APP_INDEX
from corehq.util.view_utils import absolute_reverse

from .analytics.esaccessors import (
    get_form_ids_having_multimedia,
    scroll_case_names,
)
from .export import save_metadata_export_to_tempfile
from .models import (
    ReportConfig,
    FormExportSchema,
    ReportNotification,
    UnsupportedScheduledReportError,
)

from .scheduled import get_scheduled_report_ids
import six
from six.moves import map
from six.moves import filter
from io import open


logging = get_task_logger(__name__)
EXPIRE_TIME = 60 * 60 * 24


def send_delayed_report(report_id):
    """
    Sends a scheduled report, via celery background task.
    """
    domain = ReportNotification.get(report_id).domain
    if (
        settings.SERVER_ENVIRONMENT == 'production' and
        any(re.match(pattern, domain) for pattern in settings.THROTTLE_SCHED_REPORTS_PATTERNS)
    ):
        # This is to prevent a few scheduled reports from clogging up
        # the background queue.
        # https://manage.dimagi.com/default.asp?270029#BugEvent.1457969
        send_report_throttled.delay(report_id)
    else:
        send_report.delay(report_id)


@task(serializer='pickle', queue='background_queue', ignore_result=True)
def send_report(notification_id):
    notification = ReportNotification.get(notification_id)
    try:
        notification.send()
    except UnsupportedScheduledReportError:
        pass


@task(serializer='pickle', queue='send_report_throttled', ignore_result=True)
def send_report_throttled(notification_id):
    send_report(notification_id)


@task(serializer='pickle')
def create_metadata_export(download_id, domain, format, filename, datespan=None, user_ids=None):
    tmp_path = save_metadata_export_to_tempfile(domain, format, datespan, user_ids)

    class FakeCheckpoint(object):
        # for some silly reason the export cache function wants an object that looks like this
        # so just hack around it with this stub class rather than do a larger rewrite

        def __init__(self, domain):
            self.domain = domain

        @property
        def get_id(self):
            return '%s-form-metadata' % self.domain

    return cache_file_to_be_served(Temp(tmp_path), FakeCheckpoint(domain), download_id, format, filename)


@periodic_task(serializer='pickle',
    run_every=crontab(hour="*", minute="*/15", day_of_week="*"),
    queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'),
)
def daily_reports():
    for report_id in get_scheduled_report_ids('daily'):
        send_delayed_report(report_id)


@periodic_task(serializer='pickle',
    run_every=crontab(hour="*", minute="*/15", day_of_week="*"),
    queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'),
)
def weekly_reports():
    for report_id in get_scheduled_report_ids('weekly'):
        send_delayed_report(report_id)


@periodic_task(serializer='pickle',
    run_every=crontab(hour="*", minute="*/15", day_of_week="*"),
    queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'),
)
def monthly_reports():
    for report_id in get_scheduled_report_ids('monthly'):
        send_delayed_report(report_id)


@task(serializer='pickle', queue=SAVED_EXPORTS_QUEUE, ignore_result=True)
def rebuild_export_async(config, schema):
    rebuild_export(config, schema)


@periodic_task(serializer='pickle', run_every=crontab(hour="22", minute="0", day_of_week="*"), queue='background_queue')
def update_calculated_properties():
    results = DomainES().fields(["name", "_id", "cp_last_updated"]).scroll()
    all_stats = all_domain_stats()
    for r in results:
        dom = r["name"]
        try:
            last_form_submission = CALC_FNS["last_form_submission"](dom, False)
            if _skip_updating_domain_stats(r.get("cp_last_updated"), last_form_submission):
                continue
            props = calced_props(dom, r["_id"], all_stats)
            if props['cp_first_form'] is None:
                del props['cp_first_form']
            if props['cp_last_form'] is None:
                del props['cp_last_form']
            if props['cp_300th_form'] is None:
                del props['cp_300th_form']
            send_to_elasticsearch("domains", props, es_merge_update=True)
        except Exception as e:
            notify_exception(None, message='Domain {} failed on stats calculations with {}'.format(dom, e))


def _skip_updating_domain_stats(last_updated=None, last_form_submission=None):
    """
    Skip domain if no forms submitted in the last day
    AND stats were updated less than a week ago.

    :return: True to skip domain
     """
    if not last_updated:
        return False

    last_updated_ago = datetime.utcnow() - iso_string_to_datetime(last_updated)
    if last_form_submission:
        last_form_ago = datetime.utcnow() - iso_string_to_datetime(last_form_submission)
        new_data = last_form_ago < timedelta(days=1)
    else:
        new_data = False
    return last_updated_ago < timedelta(days=7) and not new_data


def is_app_active(app_id, domain):
    return app_has_been_submitted_to_in_last_30_days(domain, app_id)


@periodic_task(serializer='pickle', run_every=crontab(hour="2", minute="0", day_of_week="*"), queue='background_queue')
def apps_update_calculated_properties():
    es = get_es_new()
    q = {"filter": {"and": [{"missing": {"field": "copy_of"}}]}}
    results = stream_es_query(q=q, es_index='apps', size=999999, chunksize=500)
    for r in results:
        props = {"cp_is_active": is_app_active(r["_id"], r["_source"]["domain"])}
        es.update(APP_INDEX, ES_META['apps'].type, r["_id"], body={"doc": props})


@task(serializer='pickle', bind=True, default_retry_delay=15 * 60, max_retries=10, acks_late=True)
def send_email_report(self, recipient_emails, domain, report_slug, report_type,
                      request_data, once, cleaned_data):
    """
    Function invokes send_HTML_email to email the html text report.
    If the report is too large to fit into email then a download link is
    sent via email to download report
    :Parameter recipient_list:
            list of recipient to whom email is to be sent
    :Parameter domain:
            domain name
    :Parameter report_slug:
            report slug
    :Parameter report_type:
            type of the report
    :Parameter request_data:
            Dict containing request data
    :Parameter once
            boolean argument specifying whether the report is once off report
            or scheduled report
    :Parameter cleaned_data:
            Dict containing cleaned data from the submitted form
    """
    from corehq.apps.reports.views import _render_report_configs, render_full_report_notification

    user_id = request_data['couch_user']
    couch_user = CouchUser.get_by_user_id(user_id)
    mock_request = HttpRequest()

    mock_request.method = 'GET'
    mock_request.GET = request_data['GET']

    config = ReportConfig()

    # see ReportConfig.query_string()
    object.__setattr__(config, '_id', 'dummy')
    config.name = _("Emailed report")
    config.report_type = report_type
    config.report_slug = report_slug
    config.owner_id = user_id
    config.domain = domain

    config.start_date = request_data['datespan'].startdate.date()
    if request_data['datespan'].enddate:
        config.date_range = 'range'
        config.end_date = request_data['datespan'].enddate.date()
    else:
        config.date_range = 'since'

    GET = dict(request_data['GET'].iterlists())
    exclude = ['startdate', 'enddate', 'subject', 'send_to_owner', 'notes', 'recipient_emails']
    filters = {}
    for field in GET:
        if field not in exclude:
            filters[field] = GET.get(field)

    config.filters = filters

    subject = cleaned_data['subject'] or _("Email report from CommCare HQ")

    content = _render_report_configs(
        mock_request, [config], domain, user_id, couch_user, True, lang=couch_user.language,
        notes=cleaned_data['notes'], once=once
    )[0]
    body = render_full_report_notification(None, content).content

    try:
        for recipient in recipient_emails:
            send_HTML_email(subject, recipient,
                            body, email_from=settings.DEFAULT_FROM_EMAIL,
                            smtp_exception_skip_list=[522])

    except Exception as er:
        if getattr(er, 'smtp_code', None) == 522:
            # If the smtp server rejects the email because of its large size.
            # Then sends the report download link in the email.
            report_state = dict(request=request_data,
                                request_params=json_request(request_data['GET']),
                                domain=domain,
                                context={})
            export_all_rows_task(config.report, report_state, recipient_list=recipient_emails)
        else:
            self.retry(exc=er)


@task(serializer='pickle', ignore_result=True)
def export_all_rows_task(ReportClass, report_state, recipient_list=None):
    report = object.__new__(ReportClass)
    report.__setstate__(report_state)

    # need to set request
    setattr(report.request, 'REQUEST', {})

    file = report.excel_response
    report_class = report.__class__.__module__ + '.' + report.__class__.__name__
    hash_id = _store_excel_in_redis(report_class, file)

    if not recipient_list:
        recipient_list = [report.request.couch_user.get_email()]

    for recipient in recipient_list:
        _send_email(report.request.couch_user, report, hash_id, recipient=recipient)


def _send_email(user, report, hash_id, recipient):
    domain = report.domain or user.get_domains()[0]
    link = absolute_reverse("export_report", args=[domain, str(hash_id),
                                                   report.export_format])

    send_report_download_email(report.name, recipient, link)


def _store_excel_in_redis(report_class, file):
    hash_id = uuid.uuid4().hex

    r = get_redis_client()
    r.set(hash_id, [report_class, file.getvalue()])
    r.expire(hash_id, EXPIRE_TIME)

    return hash_id


@task(serializer='pickle')
def build_form_multimedia_zip(
        domain,
        xmlns,
        startdate,
        enddate,
        app_id,
        export_id,
        zip_name,
        download_id,
        export_is_legacy,
        user_types=None,
        group=None):

    form_ids = get_form_ids_having_multimedia(
        domain,
        app_id,
        xmlns,
        parse(startdate),
        parse(enddate),
        group=group,
        user_types=user_types,
    )
    properties = _get_export_properties(export_id, export_is_legacy)

    if not app_id:
        zip_name = 'Unrelated Form'
    forms_info = list()
    for form in FormAccessors(domain).iter_forms(form_ids):
        if not zip_name:
            zip_name = unidecode(form.name or 'unknown form')
        forms_info.append(_extract_form_attachment_info(form, properties))

    num_forms = len(forms_info)
    DownloadBase.set_progress(build_form_multimedia_zip, 0, num_forms)

    case_id_to_name = _get_case_names(
        domain,
        set.union(*[form_info['case_ids'] for form_info in forms_info]) if forms_info else set(),
    )

    use_transfer = settings.SHARED_DRIVE_CONF.transfer_enabled
    if use_transfer:
        fpath = _get_download_file_path(xmlns, startdate, enddate, export_id, app_id, num_forms)
    else:
        _, fpath = tempfile.mkstemp()

    _write_attachments_to_file(fpath, use_transfer, num_forms, forms_info, case_id_to_name)
    filename = "{}.zip".format(zip_name)
    expose_download(use_transfer, fpath, filename, download_id, 'zip')
    DownloadBase.set_progress(build_form_multimedia_zip, num_forms, num_forms)


def _get_case_names(domain, case_ids):
    case_id_to_name = {c: c for c in case_ids}
    for case in scroll_case_names(domain, case_ids):
        if case.get('name'):
            case_id_to_name[case.get('_id')] = case.get('name')
    return case_id_to_name


def _get_download_file_path(xmlns, startdate, enddate, export_id, app_id, num_forms):
    params = '_'.join(map(str, [xmlns, startdate, enddate, export_id, num_forms]))
    fname = '{}-{}'.format(app_id, hashlib.md5(params).hexdigest())
    fpath = os.path.join(settings.SHARED_DRIVE_CONF.transfer_dir, fname)
    return fpath


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


def _write_attachments_to_file(fpath, use_transfer, num_forms, forms_info, case_id_to_name):

    if not (os.path.isfile(fpath) and use_transfer):  # Don't rebuild the file if it is already there
        with open(fpath, 'wb') as zfile:
            with zipfile.ZipFile(zfile, 'w') as multimedia_zipfile:
                for form_number, form_info in enumerate(forms_info):
                    form = form_info['form']
                    for attachment in form_info['attachments']:
                        filename = _format_filename(
                            form_info,
                            attachment['question_id'],
                            attachment['extension'],
                            case_id_to_name
                        )
                        zip_info = zipfile.ZipInfo(filename, attachment['timestamp'])
                        multimedia_zipfile.writestr(zip_info, form.get_attachment(
                            attachment['name']),
                            zipfile.ZIP_STORED
                        )
                    DownloadBase.set_progress(build_form_multimedia_zip, form_number + 1, num_forms)


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


def _get_export_properties(export_id, export_is_legacy):
    """
    Return a list of strings corresponding to form questions that are
    included in the export.
    """
    properties = set()
    if export_id:
        if export_is_legacy:
            schema = FormExportSchema.get(export_id)
            for table in schema.tables:
                properties |= _convert_legacy_indices_to_export_properties(
                    [column.index for column in table.columns]
                )
        else:
            from corehq.apps.export.models import FormExportInstance
            export = FormExportInstance.get(export_id)
            for table in export.tables:
                for column in table.columns:
                    if column.selected and column.item:
                        path_parts = [n.name for n in column.item.path]
                        path_parts = path_parts[1:] if path_parts[0] == "form" else path_parts
                        properties.add("-".join(path_parts))
    return properties


def _extract_form_attachment_info(form, properties):
    """
    This is a helper function for build_form_multimedia_zip.
    Return a dict containing information about the given form and its relevant
    attachments
    """
    def find_question_id(form, value):
        for k, v in six.iteritems(form):
            if isinstance(v, dict):
                ret = find_question_id(v, value)
                if ret:
                    return [k] + ret
            elif isinstance(v, list):
                for repeat in v:
                    ret = find_question_id(repeat, value)
                    if ret:
                        return [k] + ret
            else:
                if v == value:
                    return [k]

        return None

    unknown_number = 0

    case_blocks = extract_case_blocks(form.form_data)
    form_info = {
        'form': form,
        'attachments': [],
        'case_ids': {c['@case_id'] for c in case_blocks},
        'username': form.get_data('form/meta/username')
    }

    # TODO make form.attachments always return objects that conform to a
    # uniform interface. XFormInstance attachment values are dicts, and
    # XFormInstanceSQL attachment values are XFormAttachmentSQL objects.
    for attachment_name, attachment in six.iteritems(form.attachments):
        if hasattr(attachment, 'content_type'):
            content_type = attachment.content_type
        else:
            content_type = attachment['content_type']
        if content_type == 'text/xml':
            continue
        try:
            question_id = six.text_type(
                '-'.join(find_question_id(form.form_data, attachment_name)))
        except TypeError:
            question_id = 'unknown' + six.text_type(unknown_number)
            unknown_number += 1

        if not properties or question_id in properties:
            extension = six.text_type(os.path.splitext(attachment_name)[1])
            if hasattr(attachment, 'content_length'):
                # FormAttachmentSQL or BlobMeta
                size = attachment.content_length
            elif 'content_length' in attachment:
                # dict from BlobMeta.to_json() or possibly FormAttachmentSQL
                size = attachment['content_length']
            else:
                # couch attachment dict
                size = attachment['length']
            form_info['attachments'].append({
                'size': size,
                'name': attachment_name,
                'question_id': question_id,
                'extension': extension,
                'timestamp': form.received_on.timetuple(),
            })

    return form_info
