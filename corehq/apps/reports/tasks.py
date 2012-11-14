from datetime import datetime
from celery.log import get_task_logger
from celery.schedules import crontab
from celery.task import periodic_task, task
from django.core.cache import cache
from corehq.apps.domain.models import Domain
from corehq.apps.reports.models import (ReportNotification,
    UnsupportedScheduledReportError, HQGroupExportConfiguration,
    CaseActivityReportCache)
from couchexport.groupexports import export_for_group

logging = get_task_logger()

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
    reps = ReportNotification.view("reports/daily_notifications",
                                   key=datetime.utcnow().hour,
                                   include_docs=True).all()
    for rep in reps:
        send_report.delay(rep._id)

@periodic_task(run_every=crontab(hour="*", minute="1", day_of_week="*"))
def weekly_reports():    
    # this should get called every hour by celery
    now = datetime.utcnow()
    reps = ReportNotification.view("reports/weekly_notifications",
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

