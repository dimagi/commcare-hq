from datetime import datetime, timedelta
from dateutil.parser import parse
import hashlib
import os
import tempfile
from unidecode import unidecode
import uuid
from wsgiref.util import FileWrapper
import zipfile

from django.utils.translation import ugettext as _
from django.conf import settings

from celery.schedules import crontab
from celery.task import periodic_task
from celery.task import task
from celery.utils.log import get_task_logger

from corehq.apps.es import FormES
from corehq.apps.export.dbaccessors import get_all_daily_saved_export_instances
from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from couchexport.files import Temp
from couchexport.groupexports import export_for_group, rebuild_export
from couchexport.tasks import cache_file_to_be_served
from couchforms.analytics import app_has_been_submitted_to_in_last_30_days
from couchforms.models import XFormInstance
from dimagi.utils.couch.cache.cache_core import get_redis_client
from dimagi.utils.couch.database import iter_docs
from dimagi.utils.django.email import send_HTML_email
from dimagi.utils.logging import notify_exception
from dimagi.utils.parsing import json_format_datetime
from soil import DownloadBase
from soil.util import expose_file_download, expose_cached_download

from corehq.apps.domain.calculations import (
    _all_domain_stats,
    CALC_FNS,
    total_distinct_users,
)
from corehq.apps.es.domains import DomainES
from corehq.apps.indicators.utils import get_mvp_domains
from corehq.elastic import (
    stream_es_query,
    send_to_elasticsearch,
    get_es_new, ES_META)
from corehq.pillows.mappings.app_mapping import APP_INDEX
from corehq.util.files import file_extention_from_filename
from corehq.util.view_utils import absolute_reverse

from .dbaccessors import get_all_hq_group_export_configs
from .export import save_metadata_export_to_tempfile
from .models import (
    FormExportSchema,
    HQGroupExportConfiguration,
    ReportNotification,
    UnsupportedScheduledReportError,
)
from .scheduled import get_scheduled_reports


logging = get_task_logger(__name__)
EXPIRE_TIME = 60 * 60 * 24


def send_delayed_report(report):
    """
    Sends a scheduled report, via  celery background task.
    """
    send_report.apply_async(args=[report._id], queue=get_report_queue(report))


def get_report_queue(report):
    # This is a super-duper hacky, hard coded way to deal with the fact that MVP reports
    # consistently crush the celery queue for everyone else.
    # Just send them to their own longrunning background queue
    if report.domain in get_mvp_domains():
        return 'background_queue'
    else:
        return 'celery'


@task(ignore_result=True)
def send_report(notification_id):
    notification = ReportNotification.get(notification_id)
    try:
        notification.send()
    except UnsupportedScheduledReportError:
        pass


@task
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


@periodic_task(
    run_every=crontab(hour="*", minute="*/15", day_of_week="*"),
    queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'),
)
def daily_reports():
    for rep in get_scheduled_reports('daily'):
        send_delayed_report(rep)


@periodic_task(
    run_every=crontab(hour="*", minute="*/15", day_of_week="*"),
    queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'),
)
def weekly_reports():
    for rep in get_scheduled_reports('weekly'):
        send_delayed_report(rep)


@periodic_task(
    run_every=crontab(hour="*", minute="*/15", day_of_week="*"),
    queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'),
)
def monthly_reports():
    for rep in get_scheduled_reports('monthly'):
        send_delayed_report(rep)


@periodic_task(run_every=crontab(hour=[22], minute="0", day_of_week="*"), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE','celery'))
def saved_exports():
    for group_config in get_all_hq_group_export_configs():
        export_for_group_async.delay(group_config)

    for daily_saved_export in get_all_daily_saved_export_instances():
        from corehq.apps.export.tasks import rebuild_export_task
        last_access_cutoff = datetime.utcnow() - timedelta(days=settings.SAVED_EXPORT_ACCESS_CUTOFF)
        rebuild_export_task.delay(daily_saved_export, last_access_cutoff)


@task(queue='background_queue', ignore_result=True)
def rebuild_export_task(groupexport_id, index, last_access_cutoff=None, filter=None):
    group_config = HQGroupExportConfiguration.get(groupexport_id)
    config, schema = group_config.all_exports[index]
    rebuild_export(config, schema, last_access_cutoff, filter=filter)


@task(queue='saved_exports_queue', ignore_result=True)
def export_for_group_async(group_config):
    # exclude exports not accessed within the last 7 days
    last_access_cutoff = datetime.utcnow() - timedelta(days=settings.SAVED_EXPORT_ACCESS_CUTOFF)
    export_for_group(group_config, last_access_cutoff=last_access_cutoff)


@task(queue='saved_exports_queue', ignore_result=True)
def rebuild_export_async(config, schema):
    rebuild_export(config, schema)


@periodic_task(run_every=crontab(hour="22", minute="0", day_of_week="*"), queue='background_queue')
def update_calculated_properties():
    results = DomainES().is_snapshot(False).fields(["name", "_id"]).run().hits
    all_stats = _all_domain_stats()
    for r in results:
        dom = r["name"]
        try:
            calced_props = {
                "_id": r["_id"],
                "cp_n_web_users": int(all_stats["web_users"].get(dom, 0)),
                "cp_n_active_cc_users": int(CALC_FNS["mobile_users"](dom)),
                "cp_n_cc_users": int(all_stats["commcare_users"].get(dom, 0)),
                "cp_n_active_cases": int(CALC_FNS["cases_in_last"](dom, 120)),
                "cp_n_users_submitted_form": total_distinct_users([dom]),
                "cp_n_inactive_cases": int(CALC_FNS["inactive_cases_in_last"](dom, 120)),
                "cp_n_30_day_cases": int(CALC_FNS["cases_in_last"](dom, 30)),
                "cp_n_60_day_cases": int(CALC_FNS["cases_in_last"](dom, 60)),
                "cp_n_90_day_cases": int(CALC_FNS["cases_in_last"](dom, 90)),
                "cp_n_cases": int(all_stats["cases"].get(dom, 0)),
                "cp_n_forms": int(all_stats["forms"].get(dom, 0)),
                "cp_n_forms_30_d": int(CALC_FNS["forms_in_last"](dom, 30)),
                "cp_n_forms_60_d": int(CALC_FNS["forms_in_last"](dom, 60)),
                "cp_n_forms_90_d": int(CALC_FNS["forms_in_last"](dom, 90)),
                "cp_first_form": CALC_FNS["first_form_submission"](dom, False),
                "cp_last_form": CALC_FNS["last_form_submission"](dom, False),
                "cp_is_active": CALC_FNS["active"](dom),
                "cp_has_app": CALC_FNS["has_app"](dom),
                "cp_last_updated": json_format_datetime(datetime.utcnow()),
                "cp_n_in_sms": int(CALC_FNS["sms"](dom, "I")),
                "cp_n_out_sms": int(CALC_FNS["sms"](dom, "O")),
                "cp_n_sms_ever": int(CALC_FNS["sms_in_last"](dom)),
                "cp_n_sms_30_d": int(CALC_FNS["sms_in_last"](dom, 30)),
                "cp_n_sms_60_d": int(CALC_FNS["sms_in_last"](dom, 60)),
                "cp_n_sms_90_d": int(CALC_FNS["sms_in_last"](dom, 90)),
                "cp_sms_ever": int(CALC_FNS["sms_in_last_bool"](dom)),
                "cp_sms_30_d": int(CALC_FNS["sms_in_last_bool"](dom, 30)),
                "cp_n_sms_in_30_d": int(CALC_FNS["sms_in_in_last"](dom, 30)),
                "cp_n_sms_in_60_d": int(CALC_FNS["sms_in_in_last"](dom, 60)),
                "cp_n_sms_in_90_d": int(CALC_FNS["sms_in_in_last"](dom, 90)),
                "cp_n_sms_out_30_d": int(CALC_FNS["sms_out_in_last"](dom, 30)),
                "cp_n_sms_out_60_d": int(CALC_FNS["sms_out_in_last"](dom, 60)),
                "cp_n_sms_out_90_d": int(CALC_FNS["sms_out_in_last"](dom, 90)),
                "cp_n_j2me_30_d": int(CALC_FNS["j2me_forms_in_last"](dom, 30)),
                "cp_n_j2me_60_d": int(CALC_FNS["j2me_forms_in_last"](dom, 60)),
                "cp_n_j2me_90_d": int(CALC_FNS["j2me_forms_in_last"](dom, 90)),
                "cp_j2me_90_d_bool": int(CALC_FNS["j2me_forms_in_last_bool"](dom, 90)),
                "cp_300th_form": CALC_FNS["300th_form_submission"](dom)
            }
            if calced_props['cp_first_form'] is None:
                del calced_props['cp_first_form']
            if calced_props['cp_last_form'] is None:
                del calced_props['cp_last_form']
            if calced_props['cp_300th_form'] is None:
                del calced_props['cp_300th_form']
            send_to_elasticsearch("domains", calced_props)
        except Exception, e:
            notify_exception(None, message='Domain {} failed on stats calculations with {}'.format(dom, e))


def is_app_active(app_id, domain):
    return app_has_been_submitted_to_in_last_30_days(domain, app_id)


@periodic_task(run_every=crontab(hour="2", minute="0", day_of_week="*"), queue='background_queue')
def apps_update_calculated_properties():
    es = get_es_new()
    q = {"filter": {"and": [{"missing": {"field": "copy_of"}}]}}
    results = stream_es_query(q=q, es_index='apps', size=999999, chunksize=500)
    for r in results:
        calced_props = {"cp_is_active": is_app_active(r["_id"], r["_source"]["domain"])}
        es.update(APP_INDEX, ES_META['apps'].type, r["_id"], body={"doc": calced_props})


@task(ignore_result=True)
def export_all_rows_task(ReportClass, report_state):
    report = object.__new__(ReportClass)
    report.__setstate__(report_state)

    # need to set request
    setattr(report.request, 'REQUEST', {})

    file = report.excel_response
    hash_id = _store_excel_in_redis(file)
    _send_email(report.request.couch_user, report, hash_id)


def _send_email(user, report, hash_id):
    domain = report.domain or user.get_domains()[0]
    link = absolute_reverse("export_report", args=[domain, str(hash_id),
                                                   report.export_format])

    title = "%s: Requested export excel data"
    body = "The export you requested for the '%s' report is ready.<br>" \
           "You can download the data at the following link: %s<br><br>" \
           "Please remember that this link will only be active for 24 hours."

    send_HTML_email(
        _(title) % report.name,
        user.get_email(),
        _(body) % (report.name, "<a href='%s'>%s</a>" % (link, link)),
        email_from=settings.DEFAULT_FROM_EMAIL
    )


def _store_excel_in_redis(file):
    hash_id = uuid.uuid4().hex

    r = get_redis_client()
    r.set(hash_id, file.getvalue())
    r.expire(hash_id, EXPIRE_TIME)

    return hash_id


@task
def build_form_multimedia_zip(domain, xmlns, startdate, enddate, app_id,
                              export_id, zip_name, download_id, export_is_legacy):

    form_ids = _get_form_ids(domain, app_id, xmlns, startdate, enddate, export_is_legacy)
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

    use_transfer = settings.SHARED_DRIVE_CONF.transfer_enabled
    if use_transfer:
        fpath = _get_download_file_path(xmlns, startdate, enddate, export_id, app_id, num_forms)
    else:
        _, fpath = tempfile.mkstemp()

    _write_attachments_to_file(fpath, use_transfer, num_forms, forms_info)
    _expose_download(fpath, use_transfer, zip_name, download_id, num_forms)


def _get_download_file_path(xmlns, startdate, enddate, export_id, app_id, num_forms):
    params = '_'.join(map(str, [xmlns, startdate, enddate, export_id, num_forms]))
    fname = '{}-{}'.format(app_id, hashlib.md5(params).hexdigest())
    fpath = os.path.join(settings.SHARED_DRIVE_CONF.transfer_dir, fname)
    return fpath


def _expose_download(fpath, use_transfer, zip_name, download_id, num_forms):
    common_kwargs = dict(
        mimetype='application/zip',
        content_disposition='attachment; filename="{fname}.zip"'.format(fname=zip_name),
        download_id=download_id,
    )

    if use_transfer:
        expose_file_download(
            fpath,
            use_transfer=use_transfer,
            **common_kwargs
        )
    else:
        expose_cached_download(
            FileWrapper(open(fpath)),
            expiry=(1 * 60 * 60),
            file_extension=file_extention_from_filename(fpath),
            **common_kwargs
        )

    DownloadBase.set_progress(build_form_multimedia_zip, num_forms, num_forms)


def _write_attachments_to_file(fpath, use_transfer, num_forms, forms_info):

    def filename(form_info, question_id, extension):
        return u"{}-{}-{}{}".format(
            unidecode(question_id),
            form_info['user'],
            form_info['id'],
            extension
        )

    if not (os.path.isfile(fpath) and use_transfer):  # Don't rebuild the file if it is already there
        with open(fpath, 'wb') as zfile:
            with zipfile.ZipFile(zfile, 'w') as z:
                for form_number, form_info in enumerate(forms_info):
                    f = form_info['form']
                    for a in form_info['attachments']:
                        fname = filename(form_info, a['question_id'], a['extension'])
                        zi = zipfile.ZipInfo(fname, a['timestamp'])
                        z.writestr(zi, f.get_attachment(a['name']), zipfile.ZIP_STORED)
                    DownloadBase.set_progress(build_form_multimedia_zip, form_number + 1, num_forms)


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
                # - in question id is replaced by . in excel exports
                properties |= {c.display.replace('.', '-') for c in
                               table.columns}
        else:
            from corehq.apps.export.models import FormExportInstance
            export = FormExportInstance.get(export_id)
            for table in export.tables:
                for column in table.columns:
                    if column.item:
                        path_parts = [n.name for n in column.item.path]
                        path_parts = path_parts[1:] if path_parts[0] == "form" else path_parts
                        properties.add("-".join(path_parts))
    return properties


def _get_form_ids(domain, app_id, xmlns, startdate, enddate, export_is_legacy):
    """
    Return a list of form ids.
    Each form has a multimedia attachment and meets the given filters.
    """
    def iter_attachments(form):
        if form.get('_attachments'):
            for value in form['_attachments'].values():
                yield value
        if form.get('external_blobs'):
            for value in form['external_blobs'].values():
                yield value
    if not export_is_legacy:
        query = (FormES()
                 .domain(domain)
                 .app(app_id)
                 .xmlns(xmlns)
                 .submitted(gte=parse(startdate), lte=parse(enddate))
                 .remove_default_filter("has_user")
                 .source(['_attachments', 'external_blobs', '_id']))
        form_ids = set()
        for form in query.scroll():
            for attachment in iter_attachments(form):
                if attachment['content_type'] != "text/xml":
                    form_ids.add(form['_id'])
    else:
        key = [domain, app_id, xmlns]
        form_ids = {
            f['id'] for f in
            XFormInstance.get_db().view(
                "attachments/attachments",
                start_key=key + [startdate],
                end_key=key + [enddate, {}],
                reduce=False
            )
        }
    return form_ids


def _extract_form_attachment_info(form, properties):
    """
    This is a helper function for build_form_multimedia_zip.
    Return a dict containing information about the given form and its relevant
    attachments
    """
    def find_question_id(form, value):
        for k, v in form.iteritems():
            if isinstance(v, dict):
                ret = find_question_id(v, value)
                if ret:
                    return [k] + ret
            else:
                if v == value:
                    return [k]

        return None

    unknown_number = 0

    form_info = {
        'form': form,
        'attachments': list(),
        'name': form.name or "unknown form",
        'user': form.user_id or "unknown_user",
        'id': form.form_id,
    }

    for attachment_name, attachment in form.attachments.iteritems():
        try:
            content_type = attachment.content_type
        except AttributeError:
            content_type = attachment['content_type']
        if content_type == 'text/xml':
            continue
        try:
            question_id = unicode(
                u'-'.join(find_question_id(form.form_data, attachment_name)))
        except TypeError:
            question_id = u'unknown' + unicode(unknown_number)
            unknown_number += 1

        if not properties or question_id in properties:
            extension = unicode(os.path.splitext(attachment_name)[1])
            try:
                size = attachment.content_length
            except AttributeError:
                size = attachment['length']
            form_info['attachments'].append({
                'size': size,
                'name': attachment_name,
                'question_id': question_id,
                'extension': extension,
                'timestamp': form.received_on.timetuple(),
            })

    return form_info
