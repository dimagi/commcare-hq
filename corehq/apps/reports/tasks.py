from datetime import datetime
from celery.log import get_task_logger
from celery.schedules import crontab
from celery.task import periodic_task, task
from corehq.apps.domain.models import Domain
from corehq.apps.hqadmin.escheck import check_cluster_health, check_case_index, CLUSTER_HEALTH, check_xform_index, check_exchange_index
from corehq.apps.reports.models import (ReportNotification,
    UnsupportedScheduledReportError, HQGroupExportConfiguration,
    CaseActivityReportCache)
from couchexport.groupexports import export_for_group
from dimagi.utils.logging import notify_exception

logging = get_task_logger()

@periodic_task(run_every=crontab(hour=[8,14], minute="0", day_of_week="*"))
def check_es_index():
    """
    Verify that the Case and soon to be added XForm Elastic indices are up to date with what's in couch

    This code is also called in the HQ admin page as well
    """

    es_status = {}
    es_status.update(check_cluster_health())
    es_status.update(check_case_index())
    es_status.update(check_xform_index())
    es_status.update(check_exchange_index())

    do_notify = False
    message = []
    if es_status[CLUSTER_HEALTH] == 'red':
        do_notify=True
        message.append("Cluster health is red - something is up with the ES machine")

    for prefix in ['hqcases', 'xforms','cc_exchange']:
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

@periodic_task(run_every=crontab(hour="*", minute="0", day_of_week="*"))
def daily_reports():    
    # this should get called every hour by celery
    reps = ReportNotification.view("reportconfig/daily_notifications",
                                   key=datetime.utcnow().hour,
                                   include_docs=True).all()
    for rep in reps:
        send_report.delay(rep._id)

@periodic_task(run_every=crontab(hour="*", minute="1", day_of_week="*"))
def weekly_reports():    
    # this should get called every hour by celery
    now = datetime.utcnow()
    reps = ReportNotification.view("reportconfig/weekly_notifications",
                                   key=[now.weekday(), now.hour],
                                   include_docs=True).all()
    for rep in reps:
        send_report.delay(rep._id)

@periodic_task(run_every=crontab(hour=[0,12], minute="0", day_of_week="*"))
def saved_exports():    
    for row in HQGroupExportConfiguration.view("groupexport/by_domain", reduce=False).all():
        export_for_group(row["id"], "couch")



@periodic_task(run_every=crontab(hour=range(0,23,3), minute="0"))
def build_case_activity_report():
    logging.info("Building Case Activity Reports.")
    all_domains = Domain.get_all()
    for domain in all_domains:
        CaseActivityReportCache.build_report(domain)
