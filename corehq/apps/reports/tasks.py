from django.utils.translation import ugettext as _
from datetime import datetime, timedelta
import uuid

from celery.schedules import crontab
from celery.task import periodic_task
from corehq.apps.reports.scheduled import get_scheduled_reports
from corehq.util.view_utils import absolute_reverse
from couchexport.files import Temp
from couchexport.groupexports import export_for_group, rebuild_export
from dimagi.utils.couch.database import get_db
from dimagi.utils.logging import notify_exception
from couchexport.tasks import cache_file_to_be_served
from celery.task import task
from celery.utils.log import get_task_logger
from dimagi.utils.couch import get_redis_client
from dimagi.utils.django.email import send_HTML_email

from corehq.apps.domain.calculations import CALC_FNS, _all_domain_stats, total_distinct_users
from corehq.apps.hqadmin.escheck import (
    CLUSTER_HEALTH,
    check_case_es_index,
    check_es_cluster_health,
    check_reportcase_es_index,
    check_reportxform_es_index,
    check_xform_es_index,
)
from corehq.apps.reports.export import save_metadata_export_to_tempfile
from corehq.apps.reports.models import (
    HQGroupExportConfiguration,
    ReportNotification,
    UnsupportedScheduledReportError,
)
from corehq.elastic import get_es, ES_URLS, stream_es_query
from corehq.pillows.mappings.app_mapping import APP_INDEX
from corehq.pillows.mappings.domain_mapping import DOMAIN_INDEX
from corehq.apps.users.models import WebUser
from dimagi.utils.parsing import json_format_datetime
import settings


logging = get_task_logger(__name__)
EXPIRE_TIME = 60 * 60 * 24

@periodic_task(run_every=crontab(hour="*/6", minute="0", day_of_week="*"), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE','celery'))
def check_es_index():
    """
    Verify that the Case and soon to be added XForm Elastic indices are up to date with what's in couch

    This code is also called in the HQ admin page as well
    """

    es_status = {}
    es_status.update(check_es_cluster_health())

    es_status.update(check_case_es_index())
    es_status.update(check_xform_es_index())

    es_status.update(check_reportcase_es_index())
    es_status.update(check_reportxform_es_index())

    do_notify = False
    message = []
    if es_status[CLUSTER_HEALTH] == 'red':
        do_notify = True
        message.append("Cluster health is red - something is up with the ES machine")

    for index in es_status.keys():
        if index == CLUSTER_HEALTH:
            continue
        pillow_status = es_status[index]
        if not pillow_status['status']:
            do_notify = True
            message.append(
                "Elasticsearch %s Index Issue: %s" % (index, es_status[index]['message']))

    if do_notify:
        message.append(
            "This alert can give false alarms due to timing lag, so please double check "
            + absolute_reverse("system_info")
            + " and the Elasticsearch Status section to make sure."
        )
        notify_exception(None, message='\n'.join(message))


@task
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


@periodic_task(run_every=crontab(hour="*", minute="*/30", day_of_week="*"), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE','celery'))
def daily_reports():
    for rep in get_scheduled_reports('daily'):
        send_report.delay(rep._id)


@periodic_task(run_every=crontab(hour="*", minute="*/30", day_of_week="*"), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE','celery'))
def weekly_reports():
    for rep in get_scheduled_reports('weekly'):
        send_report.delay(rep._id)


@periodic_task(run_every=crontab(hour="*", minute="*/30", day_of_week="*"), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE','celery'))
def monthly_reports():
    for rep in get_scheduled_reports('monthly'):
        send_report.delay(rep._id)


@periodic_task(run_every=crontab(hour=[22], minute="0", day_of_week="*"), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE','celery'))
def saved_exports():
    for group_config in HQGroupExportConfiguration.view("groupexport/by_domain", reduce=False,
                                                        include_docs=True).all():
        export_for_group_async.delay(group_config, 'couch')


@task(queue='saved_exports_queue')
def export_for_group_async(group_config, output_dir):
    # exclude exports not accessed within the last 7 days
    last_access_cutoff = datetime.utcnow() - timedelta(days=settings.SAVED_EXPORT_ACCESS_CUTOFF)
    export_for_group(group_config, output_dir, last_access_cutoff=last_access_cutoff)


@task(queue='saved_exports_queue')
def rebuild_export_async(config, schema, output_dir):
    rebuild_export(config, schema, output_dir)


@periodic_task(run_every=crontab(hour="12, 22", minute="0", day_of_week="*"), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE','celery'))
def update_calculated_properties():
    es = get_es()

    q = {"filter": {"and": [
        {"term": {"doc_type": "Domain"}},
        {"term": {"is_snapshot": False}}
    ]}}
    results = stream_es_query(q=q, es_url=ES_URLS["domains"], size=999999, chunksize=500, fields=["name"])
    all_stats = _all_domain_stats()
    for r in results:
        dom = r["fields"]["name"]
        calced_props = {
            "cp_n_web_users": int(all_stats["web_users"][dom]),
            "cp_n_active_cc_users": int(CALC_FNS["mobile_users"](dom)),
            "cp_n_cc_users": int(all_stats["commcare_users"][dom]),
            "cp_n_active_cases": int(CALC_FNS["cases_in_last"](dom, 120)),
            "cp_n_users_submitted_form": total_distinct_users([dom]),
            "cp_n_inactive_cases": int(CALC_FNS["inactive_cases_in_last"](dom, 120)),
            "cp_n_60_day_cases": int(CALC_FNS["cases_in_last"](dom, 60)),
            "cp_n_cases": int(all_stats["cases"][dom]),
            "cp_n_forms": int(all_stats["forms"][dom]),
            "cp_first_form": CALC_FNS["first_form_submission"](dom, False),
            "cp_last_form": CALC_FNS["last_form_submission"](dom, False),
            "cp_is_active": CALC_FNS["active"](dom),
            "cp_has_app": CALC_FNS["has_app"](dom),
            "cp_last_updated": json_format_datetime(datetime.utcnow()),
            "cp_n_in_sms": int(CALC_FNS["sms"](dom, "I")),
            "cp_n_out_sms": int(CALC_FNS["sms"](dom, "O")),
            "cp_n_sms_ever": int(CALC_FNS["sms_in_last"](dom)),
            "cp_n_sms_30_d": int(CALC_FNS["sms_in_last"](dom, 30)),
            "cp_sms_ever": int(CALC_FNS["sms_in_last_bool"](dom)),
            "cp_sms_30_d": int(CALC_FNS["sms_in_last_bool"](dom, 30)),
        }
        if calced_props['cp_first_form'] == 'No forms':
            del calced_props['cp_first_form']
            del calced_props['cp_last_form']
        es.post("%s/hqdomain/%s/_update" % (DOMAIN_INDEX, r["_id"]), data={"doc": calced_props})


def is_app_active(app_id, domain):
    now = datetime.utcnow()
    then = json_format_datetime(now - timedelta(days=30))
    now = json_format_datetime(now)

    key = ['submission app', domain, app_id]
    row = get_db().view("reports_forms/all_forms", startkey=key+[then], endkey=key+[now]).all()
    return True if row else False

@periodic_task(run_every=crontab(hour="12, 22", minute="0", day_of_week="*"), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE','celery'))
def apps_update_calculated_properties():
    es = get_es()
    q = {"filter": {"and": [{"missing": {"field": "copy_of"}}]}}
    results = stream_es_query(q=q, es_url=ES_URLS["apps"], size=999999, chunksize=500)
    for r in results:
        calced_props = {"cp_is_active": is_app_active(r["_id"], r["_source"]["domain"])}
        es.post("%s/app/%s/_update" % (APP_INDEX, r["_id"]), data={"doc": calced_props})

@task
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
