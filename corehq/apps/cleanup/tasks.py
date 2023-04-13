from django.conf import settings
from django.core.management import call_command

from celery.schedules import crontab

from corehq.apps.celery import periodic_task
from corehq.apps.cleanup.dbaccessors import (
    find_es_docs_for_deleted_domains,
    find_sql_cases_for_deleted_domains,
    find_sql_forms_for_deleted_domains,
    find_ucr_tables_for_deleted_domains,
)
from corehq.apps.cleanup.tests.util import is_monday
from corehq.apps.domain.models import Domain
from corehq.apps.hqwebapp.tasks import mail_admins_async

UNDEFINED_XMLNS_LOG_DIR = settings.LOG_HOME


@periodic_task(run_every=crontab(minute=0, hour=0), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def clear_expired_sessions():
    call_command('clearsessions')


@periodic_task(run_every=crontab(minute=0, hour=0), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def check_for_sql_cases_without_existing_domain():
    case_count_by_deleted_domain = find_sql_cases_for_deleted_domains()
    if case_count_by_deleted_domain:
        mail_admins_async.delay(
            'There exist SQL cases belonging to deleted domain(s)',
            f'{case_count_by_deleted_domain}\nConsider hard_delete_forms_and_cases_in_domain'
        )
    elif is_monday():
        mail_admins_async.delay(
            'All SQL cases belong to valid domains', ''
        )


@periodic_task(run_every=crontab(minute=0, hour=1), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def check_for_sql_forms_without_existing_domain():
    form_count_by_deleted_domain = find_sql_forms_for_deleted_domains()
    if form_count_by_deleted_domain:
        mail_admins_async.delay(
            'There exist SQL forms belonging to deleted domain(s)',
            f'{form_count_by_deleted_domain}\nConsider hard_delete_forms_and_cases_in_domain'
        )
    elif is_monday():
        mail_admins_async.delay(
            'All SQL forms belong to valid domains', ''
        )


@periodic_task(run_every=crontab(minute=0, hour=0), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def check_for_elasticsearch_data_without_existing_domain():
    es_docs_by_deleted_domain = find_es_docs_for_deleted_domains()
    if es_docs_by_deleted_domain:
        for domain, es_docs in es_docs_by_deleted_domain.items():
            mail_admins_async.delay(
                f'Deleted domain "{domain}" has remaining ES docs',
                f'{es_docs}\nConsider delete_es_docs_for_domain'
            )
    elif is_monday():
        mail_admins_async.delay(
            'All data in ES belongs to valid domains', ''
        )


@periodic_task(run_every=crontab(minute=0, hour=0), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def check_for_ucr_tables_without_existing_domain():
    deleted_domains_to_tables = find_ucr_tables_for_deleted_domains()
    if deleted_domains_to_tables:
        for deleted_domain in deleted_domains_to_tables:
            mail_admins_async.delay(
                f'Deleted domain "{deleted_domain}" has remaining UCR tables',
                f'{deleted_domains_to_tables[deleted_domain]}\nConsider manage_orphaned_ucrs'
            )
    elif is_monday():
        mail_admins_async.delay('All UCR tables belong to valid domains', '')


@periodic_task(run_every=crontab(minute=0, hour=0), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def check_for_conflicting_domains():
    """
    It should be impossible for domains to get into this state, but in the event that it does we want to know
    Other cleanup tasks depend on the assumption that a domain name only exists once across all Domain and
    Domain-Deleted doc types
    """
    current_domains = set(Domain.get_all_names())
    deleted_domains = Domain.get_deleted_domain_names()
    conflicting_domains = current_domains & deleted_domains
    if conflicting_domains:
        mail_admins_async.delay(
            'Conflicting domain names',
            'The following domains exist as both a Domain doc and Domain-Deleted doc. This should never happen.'
            f'{conflicting_domains}'
        )
