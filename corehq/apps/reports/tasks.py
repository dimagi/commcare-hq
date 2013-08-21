from datetime import datetime
from celery.schedules import crontab
from celery.task import periodic_task, task
from celery.utils.log import get_task_logger
from corehq.apps.domain.calculations import CALC_FNS, _all_domain_stats
from corehq.apps.hqadmin.escheck import check_cluster_health, check_case_index, CLUSTER_HEALTH, check_xform_index
from corehq.apps.reports.export import save_metadata_export_to_tempfile
from corehq.apps.reports.models import (ReportNotification,
    UnsupportedScheduledReportError, HQGroupExportConfiguration)
from corehq.elastic import get_es
from corehq.pillows.mappings.domain_mapping import DOMAIN_INDEX
from couchexport.groupexports import export_for_group
from dimagi.utils.logging import notify_exception
from couchexport.tasks import cache_file_to_be_served
from django.conf import settings

logging = get_task_logger(__name__)

@periodic_task(run_every=crontab(hour=[8,14], minute="0", day_of_week="*"), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE','celery'))
def check_es_index():
    """
    Verify that the Case and soon to be added XForm Elastic indices are up to date with what's in couch

    This code is also called in the HQ admin page as well
    """

    es_status = {}
    es_status.update(check_cluster_health())
    es_status.update(check_case_index())
    es_status.update(check_xform_index())

    do_notify = False
    message = []
    if es_status[CLUSTER_HEALTH] == 'red':
        do_notify=True
        message.append("Cluster health is red - something is up with the ES machine")

    for prefix in ['hqcases', 'xforms']:
        if es_status.get('%s_status' % prefix, False) == False:
            do_notify=True
            message.append("Elasticsearch %s Index Issue: %s" % (prefix, es_status['%s_message' % prefix]))

    if do_notify:
        notify_exception(None, message='\n'.join(message))


@task
def send_report(notification_id):
    notification = ReportNotification.get(notification_id)
    try:
        notification.send()
    except UnsupportedScheduledReportError:
        pass

@task
def create_metadata_export(download_id, domain, format, filename):
    tmp_path = save_metadata_export_to_tempfile(domain)

    class FakeCheckpoint(object):
        # for some silly reason the export cache function wants an object that looks like this
        # so just hack around it with this stub class rather than do a larger rewrite

        def __init__(self, domain):
            self.domain = domain

        @property
        def get_id(self):
            return '%s-form-metadata' % self.domain

    return cache_file_to_be_served(tmp_path, FakeCheckpoint(domain), download_id, format, filename)

@periodic_task(run_every=crontab(hour="*", minute="0", day_of_week="*"), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE','celery'))
def daily_reports():    
    # this should get called every hour by celery
    reps = ReportNotification.view("reportconfig/daily_notifications",
                                   key=datetime.utcnow().hour,
                                   include_docs=True).all()
    for rep in reps:
        send_report.delay(rep._id)

@periodic_task(run_every=crontab(hour="*", minute="1", day_of_week="*"), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE','celery'))
def weekly_reports():    
    # this should get called every hour by celery
    now = datetime.utcnow()
    reps = ReportNotification.view("reportconfig/weekly_notifications",
                                   key=[now.weekday(), now.hour],
                                   include_docs=True).all()
    for rep in reps:
        send_report.delay(rep._id)

@periodic_task(run_every=crontab(hour=[0,12], minute="0", day_of_week="*"), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE','celery'))
def saved_exports():    
    for row in HQGroupExportConfiguration.view("groupexport/by_domain", reduce=False).all():
        export_for_group(row["id"], "couch")

@periodic_task(run_every=crontab(hour="12, 22", minute="0", day_of_week="*"), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE','celery'))
def update_calculated_properties():
    es = get_es()

    #todo: use some sort of ES scrolling/paginating
    results = es.get(DOMAIN_INDEX + "/hqdomain/_search", data={"size": 99999})['hits']['hits']
    all_stats = _all_domain_stats()
    for r in results:
        dom = r["_source"]["name"]
        calced_props = {
            "cp_n_web_users": int(all_stats["web_users"][dom]),
            "cp_n_active_cc_users": int(CALC_FNS["mobile_users"](dom)),
            "cp_n_cc_users": int(all_stats["commcare_users"][dom]),
            "cp_n_active_cases": int(CALC_FNS["cases_in_last"](dom, 120)),
            "cp_n_inactive_cases": int(CALC_FNS["inactive_cases_in_last"](dom, 120)),
            "cp_n_60_day_cases": int(CALC_FNS["cases_in_last"](dom, 60)),
            "cp_n_cases": int(all_stats["cases"][dom]),
            "cp_n_forms": int(all_stats["forms"][dom]),
            "cp_first_form": CALC_FNS["first_form_submission"](dom, False),
            "cp_last_form": CALC_FNS["last_form_submission"](dom, False),
            "cp_is_active": CALC_FNS["active"](dom),
            "cp_has_app": CALC_FNS["has_app"](dom),
        }
        if calced_props['cp_first_form'] == 'No forms':
            del calced_props['cp_first_form']
            del calced_props['cp_last_form']
        es.post("%s/hqdomain/%s/_update" % (DOMAIN_INDEX, r["_id"]), data={"doc": calced_props})
