from django.conf import settings

from celery.schedules import crontab
from celery.utils.log import get_task_logger

from corehq import privileges
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.callcenter.indicator_sets import CallCenterIndicators
from corehq.apps.callcenter.sync_usercase import sync_usercases
from corehq.apps.callcenter.utils import (
    get_call_center_cases,
    get_call_center_domains,
    is_midnight_for_domain,
)
from corehq.apps.celery import periodic_task, task
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import CouchUser

logger = get_task_logger(__name__)


@periodic_task(run_every=crontab(minute='*/15'), queue='background_queue')
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


def bulk_sync_usercases_if_applicable(domain, user_ids):
    domain_obj = Domain.get_by_name(domain)
    if (domain_obj.call_center_config.enabled
            or domain_has_privilege(domain, privileges.USERCASE)):
        for user_id in user_ids:
            sync_usercases_task.delay(user_id, domain_obj.name)


def sync_usercases_if_applicable(domain, user, spawn_task):
    domain_obj = Domain.get_by_name(domain) if domain else None
    if not domain_obj:
        return
    if settings.UNIT_TESTING and not domain_obj:
        return
    if (domain_obj.call_center_config.enabled
            or domain_has_privilege(domain, privileges.USERCASE)):
        if spawn_task:
            sync_usercases_task.delay(user._id, domain)
        else:
            sync_usercases(user, domain)


@task(queue='background_queue')
def sync_usercases_task(user_id, domain):
    user = CouchUser.get_by_user_id(user_id)
    if user:
        sync_usercases(user, domain)
