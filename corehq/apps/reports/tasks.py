from datetime import datetime
from celery.schedules import crontab
from celery.decorators import periodic_task
from corehq.apps.reports.models import DailyReportNotification
from corehq.apps.users.models import CouchUser
from corehq.apps.reports.schedule import config
from corehq.apps.reports.schedule.html2text import html2text
from dimagi.utils.django.email import send_HTML_email

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
    
def send_report(scheduled_report, user):
    report = config.SCHEDULABLE_REPORTS[scheduled_report.report_slug]
    body = report.get_response(user.default_django_user, scheduled_report.domain)
    send_HTML_email("[%s] %s" % (scheduled_report.domain, report.title), user.default_django_user.email,
                    html2text(body), body)

def _run_reports(reps):
    for rep in reps:
        for user_id in rep.user_ids:
            user = CouchUser.get(user_id)
            send_report(rep, user)
            
            

