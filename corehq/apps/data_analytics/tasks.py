from datetime import date, datetime, timedelta, timezone

from django.conf import settings
from django.db.models import Q

from celery.schedules import crontab
from celery.utils.log import get_task_logger

from dimagi.utils.chunked import chunked
from dimagi.utils.dates import DateSpan
from dimagi.utils.logging import notify_exception

from corehq.apps.celery import periodic_task, task
from corehq.apps.data_analytics.gir_generator import GIRTableGenerator
from corehq.apps.data_analytics.malt_generator import generate_malt
from corehq.apps.data_analytics.models import DomainMetrics
from corehq.apps.data_analytics.util import (
    last_month_datespan,
    last_month_dict,
)
from corehq.apps.domain.calculations import all_domain_stats, domain_metrics
from corehq.apps.domain.models import Domain
from corehq.apps.es import DomainES, FormES, filters
from corehq.util.log import send_HTML_email
from corehq.util.metrics import metrics_gauge
from corehq.util.soft_assert import soft_assert

logger = get_task_logger(__name__)


@periodic_task(queue=settings.CELERY_PERIODIC_QUEUE, run_every=crontab(hour=1, minute=0, day_of_month='2'),
               acks_late=True, ignore_result=True)
def build_last_month_MALT():
    last_month = last_month_dict()
    domains = Domain.get_all_names()
    for chunk in chunked(domains, 1000):
        update_malt.delay(last_month, chunk)


@periodic_task(queue=settings.CELERY_PERIODIC_QUEUE, run_every=crontab(hour=2, minute=0, day_of_week='*'),
               ignore_result=True)
def update_current_MALT():
    today = date.today()
    this_month_dict = {'month': today.month, 'year': today.year}
    domains = Domain.get_all_names()
    for chunk in chunked(domains, 1000):
        update_malt.delay(this_month_dict, chunk)


@periodic_task(queue=settings.CELERY_PERIODIC_QUEUE, run_every=crontab(hour=1, minute=0, day_of_month='3'),
               acks_late=True, ignore_result=True)
def build_last_month_GIR():
    last_month = last_month_datespan()
    try:
        generator = GIRTableGenerator([last_month])
        generator.build_table()
    except Exception as e:
        soft_assert(to=[settings.DATA_EMAIL], send_to_ops=False)(False, "Error in his month's GIR generation")
        # pass it so it gets logged in celery as an error as well
        raise e

    message = 'Global impact report generation for month {} is now ready. To download go to' \
              ' http://www.commcarehq.org/hq/admin/download_gir/'.format(
                  last_month
              )
    send_HTML_email(
        'GIR data is ready',
        settings.DATA_EMAIL,
        message,
        text_content=message
    )


@task(queue='malt_generation_queue')
def update_malt(month_dict, domains):
    month = DateSpan.from_month(month_dict['month'], month_dict['year'])
    generate_malt([month], domains=domains)


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


@periodic_task(run_every=crontab(hour="22", minute="0", day_of_week="*"), queue='background_queue')
def update_domain_metrics():
    domains = get_domains_to_update()
    for chunk in chunked(domains, 5000):
        update_domain_metrics_for_domains.delay(chunk)


@task(queue='background_queue')
def update_domain_metrics_for_domains(domains):
    """
    :param domains: list of domain names
    """
    # relying on caching for efficiency
    all_stats = all_domain_stats()
    active_users_by_domain = {}
    for domain in domains:
        metrics = _update_or_create_domain_metrics(domain, all_stats)
        if metrics:
            active_users_by_domain[domain] = metrics.active_mobile_workers

    datadog_report_user_stats('commcare.active_mobile_workers.count', active_users_by_domain)


def _update_or_create_domain_metrics(domain, all_stats):
    try:
        domain_obj = Domain.get_by_name(domain)
        metrics_dict = domain_metrics(domain_obj, domain_obj['_id'], all_stats)
        metrics, __ = DomainMetrics.objects.update_or_create(
            defaults=metrics_dict,
            domain=domain_obj.name,
        )
    except Exception as e:
        notify_exception(
            None, message='Failed to create or update domain metrics for {domain}: {}'.format(e, domain=domain)
        )
        metrics = None

    return metrics


def get_domains_to_update():
    """
    Returns a list of domains that are active and meet one or more
    of the following criteria:
     - never had DomainMetrics created
     - DomainMetrics was updated over one week ago
     - new form submissions within the last day
    """
    is_domain_active = filters.term('is_active', True)
    active_domains = (
        DomainES().filter(is_domain_active)
        .terms_aggregation('name.exact', 'domain')
        .size(0).run().aggregations.domain.keys
    )

    now = datetime.now(tz=timezone.utc)
    yesterday = now - timedelta(days=1)
    domains_submitted_within_day = (
        FormES().submitted(gte=yesterday)
        .terms_aggregation('domain.exact', 'domain')
        .size(0).run().aggregations.domain.keys
    )

    last_week = now - timedelta(days=7)
    domains_up_to_date = DomainMetrics.objects.filter(
        Q(domain__in=active_domains)
        & Q(last_modified__gte=last_week)
        & ~Q(domain__in=domains_submitted_within_day)
    ).values_list('domain', flat=True)

    return set(active_domains) - set(domains_up_to_date)
