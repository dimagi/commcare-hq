from datetime import datetime
from smtplib import SMTPRecipientsRefused
from celery.log import get_task_logger
from celery.schedules import crontab
from celery.decorators import periodic_task, task
from django.http import Http404
from corehq.apps.domain.models import Domain
from corehq.apps.reports.models import DailyReportNotification,\
    HQGroupExportConfiguration, CaseActivityReportCache
from corehq.apps.users.models import CouchUser
from corehq.apps.reports.schedule.html2text import html2text
from dimagi.utils.django.email import send_HTML_email
from corehq.apps.reports.schedule.config import ScheduledReportFactory
from couchexport.groupexports import export_for_group

logging = get_task_logger()

@periodic_task(run_every=crontab(hour="*", minute="0", day_of_week="*"))
def daily_reports():    
    # this should get called every hour by celery
    reps = DailyReportNotification.view("reports/daily_notifications", 
                                        key=datetime.utcnow().hour, 
                                        include_docs=True).all()
    _run_reports(reps)

@periodic_task(run_every=crontab(hour="*", minute="1", day_of_week="*"))
def weekly_reports():    
    # this should get called every hour by celery
    now = datetime.utcnow()
    reps = DailyReportNotification.view("reports/weekly_notifications", 
                                        key=[now.weekday(), now.hour], 
                                        include_docs=True).all()
    _run_reports(reps)

@task
def send_report(scheduled_report, user):
    if isinstance(user, dict):
        user = CouchUser.wrap_correctly(user)
    try:
        report = ScheduledReportFactory.get_report(scheduled_report.report_slug)
        body = report.get_response(user, scheduled_report.domain)
        email = user.get_email()
        if email:
            send_HTML_email("%s [%s]" % (report.title, scheduled_report.domain), email,
                        html2text(body), body)
        else:
            raise SMTPRecipientsRefused(None)
    except Http404:
        # Scenario: user has been removed from the domain that they have scheduled reports for.
        # Do a scheduled report cleanup
        user_id = unicode(user.get_id)
        domain = Domain.get_by_name(scheduled_report.domain)
        user_ids = [user.get_id for user in domain.all_users()]
        if user_id not in user_ids:
            # remove the offending user from the scheduled report
            scheduled_report.user_ids.remove(user_id)
            if len(scheduled_report.user_ids) == 0:
                # there are no users with appropriate permissions left in the scheduled report,
                # so remove it
                scheduled_report.delete()
            else:
                scheduled_report.save()

@periodic_task(run_every=crontab(hour=[0,12], minute="0", day_of_week="*"))
def saved_exports():    
    for row in HQGroupExportConfiguration.view("groupexport/by_domain", reduce=False).all():
        export_for_group(row["id"], "couch")


def _run_reports(reps):
    for rep in reps:
        for user_id in rep.user_ids:
            user = CouchUser.get(user_id)
            send_report.delay(rep, user.to_json())

@periodic_task(run_every=crontab(hour=range(0,23,3), minute="0"))
def build_case_activity_report():
    all_domains = Domain.get_all()
    for domain in all_domains:
        CaseActivityReportCache.build_report(domain)
