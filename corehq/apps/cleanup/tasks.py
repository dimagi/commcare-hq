from collections import defaultdict
from datetime import datetime

from django.conf import settings
from django.core.management import call_command
from django.db import connections

from celery.schedules import crontab
from celery.task import periodic_task

from corehq.apps.accounting.models import Subscription
from corehq.apps.domain.models import Domain
from corehq.apps.es import AppES, CaseES, CaseSearchES, FormES, GroupES, UserES
from corehq.apps.hqwebapp.tasks import mail_admins_async
from corehq.form_processor.models import XFormInstanceSQL, CommCareCaseSQL
from corehq.sql_db.connections import UCR_ENGINE_ID, ConnectionManager
from corehq.sql_db.util import get_db_aliases_for_partitioned_query

UNDEFINED_XMLNS_LOG_DIR = settings.LOG_HOME


@periodic_task(run_every=crontab(minute=0, hour=0), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def clear_expired_sessions():
    call_command('clearsessions')


@periodic_task(run_every=crontab(minute=0, hour=0), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def check_for_sql_cases_without_existing_domain():
    case_count_by_missing_domain = {}
    for domain in _get_missing_domains():
        case_count = 0
        for db_name in get_db_aliases_for_partitioned_query():
            case_count += CommCareCaseSQL.objects.using(db_name).filter(domain=domain).count()
        if case_count:
            case_count_by_missing_domain[domain] = case_count

    if case_count_by_missing_domain:
        mail_admins_async.delay(
            'There exist SQL cases belonging to a missing domain',
            f'{case_count_by_missing_domain}\nConsider hard_delete_forms_and_cases_in_domain'
        )
    elif _is_monday():
        mail_admins_async.delay(
            'All SQL cases belong to valid domains', ''
        )


@periodic_task(run_every=crontab(minute=0, hour=1), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def check_for_sql_forms_without_existing_domain():
    form_count_by_missing_domain = {}
    for domain in _get_missing_domains():
        form_count = 0
        for db_name in get_db_aliases_for_partitioned_query():
            form_count += XFormInstanceSQL.objects.using(db_name).filter(domain=domain).count()
        if form_count:
            form_count_by_missing_domain[domain] = form_count

    if form_count_by_missing_domain:
        mail_admins_async.delay(
            'There exist SQL forms belonging to a missing domain',
            f'{form_count_by_missing_domain}\nConsider hard_delete_forms_and_cases_in_domain'
        )
    elif _is_monday():
        mail_admins_async.delay(
            'All SQL forms belong to valid domains', ''
        )


@periodic_task(run_every=crontab(minute=0, hour=0), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def check_for_elasticsearch_data_without_existing_domain():
    issue_found = False
    for domain_name in _get_missing_domains():
        for hqESQuery in [AppES, CaseES, CaseSearchES, FormES, GroupES, UserES]:
            query = hqESQuery().domain(domain_name)
            count = query.count()
            if query.count() != 0:
                issue_found = True
                mail_admins_async.delay(
                    'ES index "%s" contains %s items belonging to missing domain "%s"' % (
                        query.index, count, domain_name
                    ), ''
                )
    if not issue_found and _is_monday():
        mail_admins_async.delay(
            'All data in ES belongs to valid domains', ''
        )


@periodic_task(run_every=crontab(minute=0, hour=0), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def check_for_ucr_tables_without_existing_domain():
    all_domain_names = Domain.get_all_names()

    connection_name = ConnectionManager().get_django_db_alias(UCR_ENGINE_ID)
    table_names = connections[connection_name].introspection.table_names()
    ucr_table_names = [name for name in table_names if name.startswith('config_report')]

    missing_domains_to_tables = defaultdict(list)

    for ucr_table_name in ucr_table_names:
        table_domain = ucr_table_name.split('_')[2]
        if table_domain not in all_domain_names:
            missing_domains_to_tables[table_domain].append(ucr_table_name)

    if missing_domains_to_tables:
        for missing_domain in missing_domains_to_tables:
            mail_admins_async.delay(
                f'Missing domain "{missing_domain}" has remaining UCR tables',
                f'{missing_domains_to_tables[missing_domain]}\nConsider prune_old_datasources'
            )
    elif _is_monday():
        mail_admins_async.delay('All UCR tables belong to valid domains', '')


def _get_missing_domains():
    return set(_get_all_domains_that_have_ever_had_subscriptions()) - set(Domain.get_all_names())


def _get_all_domains_that_have_ever_had_subscriptions():
    return Subscription.visible_and_suppressed_objects.values_list('subscriber__domain', flat=True).distinct()


def _is_monday():
    return datetime.utcnow().isoweekday() == 1
