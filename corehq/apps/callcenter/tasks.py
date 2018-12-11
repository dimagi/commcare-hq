from __future__ import absolute_import
from __future__ import unicode_literals
from celery.schedules import crontab
from celery.task import periodic_task, task
from celery.utils.log import get_task_logger

from corehq.apps.callcenter.indicator_sets import CallCenterIndicators
from corehq.apps.callcenter.sync_user_case import sync_call_center_user_case, sync_usercase
from corehq.apps.callcenter.utils import get_call_center_domains, is_midnight_for_domain, get_call_center_cases

logger = get_task_logger(__name__)


@periodic_task(serializer='pickle', run_every=crontab(minute='*/15'), queue='background_queue')
def calculate_indicators():
    """
    Although this task runs every 15 minutes it only re-calculates the
    indicators for a domain if we're within 15 minutes after midnight in
    the domain's timezone.
    """
    domains = [
        domain
        for domain in get_call_center_domains()
        for midnight in domain.midnights()
        if is_midnight_for_domain(midnight, error_margin=20) and domain.use_fixtures
    ]
    logger.info("Calculating callcenter indicators for domains:\n{}".format(domains))
    for domain in domains:
        all_cases = get_call_center_cases(domain.name, domain.cc_case_type)
        indicator_set = CallCenterIndicators(
            domain.name,
            domain.default_timezone,
            domain.cc_case_type,
            user=None,
            override_cases=all_cases,
            override_cache=True
        )
        indicator_set.get_data()


@task(serializer='pickle')
def sync_user_cases(user):
    sync_call_center_user_case(user)
    sync_usercase(user)
