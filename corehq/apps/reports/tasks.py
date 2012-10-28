from datetime import datetime
from celery.log import get_task_logger
from celery.schedules import crontab
from celery.task import periodic_task, task
from django.core.cache import cache
from django.http import Http404
from corehq.apps.domain.models import Domain
from corehq.apps.reports.models import (DailyReportNotification,
    HQGroupExportConfiguration, CaseActivityReportCache)
from corehq.apps.users.models import CouchUser
from dimagi.utils.django.email import send_HTML_email
from couchexport.groupexports import export_for_group
from django.template.loader import render_to_string
from django.conf import settings
from django.contrib.sites.models import Site
import json

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
def send_report(notification, user):
    if isinstance(user, dict):
        user = CouchUser.wrap_correctly(user)

    email = user.get_email()
    if not email:
        raise Exception("Tried to email a user who doesn't have one")

    config = notification.config
    report_class = config.report.__module__ + '.' + config.report.__name__

    if not user.can_view_report(config.domain, report_class):
        raise Exception("Tried to send a report to a user without permissions")

    try:
        content = config.get_report_content(config.domain, user)
    except Http404:
        # Scenario: user has been removed from the domain that they have scheduled reports for.
        # Do a scheduled report cleanup
        user_id = unicode(user.get_id)
        domain = Domain.get_by_name(notification.config.domain)
        user_ids = [user._id for user in domain.all_users()]
        if user_id not in user_ids:
            notification.remove_user(user_id)
    else:
        DNS_name = "http://" + Site.objects.get(id=settings.SITE_ID).domain
        body = render_to_string("reports/report_email.html", {
            "report_body": content,
            "domain": config.domain,
            "couch_user": user.userID,
            "DNS_name": DNS_name
        })
        title = "%s [%s]" % (config.full_name, config.domain)
        
        send_HTML_email(title, email, body)

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
    logging.info("Building Case Activity Reports.")
    all_domains = Domain.get_all()
    for domain in all_domains:
        CaseActivityReportCache.build_report(domain)


@task
def report_cacher(report, context_func, cache_key,
                  current_cache=None, refresh_stale=1800, cache_timeout=3600):
    data_key = report.queried_path
    data = getattr(report, context_func)
    _cache_data(data, cache_key,
        current_cache=current_cache, refresh_stale=refresh_stale,
        cache_timeout=cache_timeout, data_key=data_key)

@task
def user_cacher(domain, cache_key,
                current_cache=None, refresh_stale=1800, cache_timeout=3600, **kwargs):
    from corehq.apps.reports.util import get_all_users_by_domain
    data = get_all_users_by_domain(domain, **kwargs)
    _cache_data(data, cache_key,
        current_cache=current_cache,
        refresh_stale=refresh_stale,
        cache_timeout=cache_timeout)


def _cache_data(data, cache_key,
                       current_cache=None, refresh_stale=1800, cache_timeout=3600, data_key="data"):
    last_cached = None
    if current_cache is not None:
        last_cached = current_cache.get('set_on')
        if not isinstance(last_cached, datetime):
            last_cached = None

    diff = None
    if last_cached is not None:
        td = datetime.utcnow() - last_cached
        diff = td.seconds + td.days * 24 * 3600

    if diff is None or diff >= refresh_stale:
        if isinstance(current_cache, dict):
            new_cache = current_cache.copy()
        else:
            new_cache = dict()
        new_cache['set_on'] = datetime.utcnow()
        new_cache[data_key] = data
        cache.set(cache_key, new_cache, cache_timeout)

