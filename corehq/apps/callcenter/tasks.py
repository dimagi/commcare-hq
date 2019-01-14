from __future__ import absolute_import
from __future__ import unicode_literals
import datetime
from celery.schedules import crontab
from celery.task import periodic_task, task
from celery.utils.log import get_task_logger
from django.conf import settings
from dimagi.utils.couch.cache.cache_core import get_redis_client

from corehq.apps.users.models import CommCareUser

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


@task(serializer='pickle', queue='background_queue')
def sync_user_cases(user_id):
    user = CommCareUser.get_by_user_id(user_id)
    if settings.UNIT_TESTING and not user.project:
        return

    # Temporary shim to clear out duplicates from the queue
    if user.last_modified < datetime.datetime(2019, 1, 14, 18):
        key = "clear-sync_user_cases-{}".format(user_id)
        client = get_redis_client()
        if client.get(key):
            return
        client.set(key, True, timeout=60 * 60 * 24 * 10)

    sync_call_center_user_case(user)
    sync_usercase(user)
