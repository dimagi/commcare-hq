from __future__ import absolute_import
from __future__ import unicode_literals
import os
import json
from time import time
from collections import defaultdict
from datetime import datetime
import six

from celery.schedules import crontab
from celery.task import periodic_task

from django.conf import settings
from django.core.management import call_command
from django.db import connections

from corehq.apps.accounting.models import Subscription
from corehq.apps.domain.models import Domain
from corehq.apps.es import AppES, CaseES, CaseSearchES, FormES, GroupES, LedgerES, UserES
from corehq.apps.hqwebapp.tasks import mail_admins_async
from corehq.apps.cleanup.management.commands.fix_xforms_with_undefined_xmlns import \
    parse_log_message, ERROR_SAVING, SET_XMLNS, MULTI_MATCH, \
    CANT_MATCH, FORM_HAS_UNDEFINED_XMLNS
from corehq.apps.users.models import WebUser
from corehq.form_processor.backends.sql.dbaccessors import CaseReindexAccessor, FormReindexAccessor
from corehq.sql_db.connections import ConnectionManager, UCR_ENGINE_ID
from io import open


UNDEFINED_XMLNS_LOG_DIR = settings.LOG_HOME


def json_handler(obj):
    if isinstance(obj, set):
        return list(obj)
    else:
        return json.JSONEncoder().default(obj)


@periodic_task(run_every=crontab(day_of_week=[1, 4], hour=0, minute=0))  # every Monday and Thursday
def fix_xforms_with_missing_xmlns():
    log_file_name = 'undefined_xmlns.{}-timestamp.log'.format(int(time()))
    log_file_path = os.path.join(UNDEFINED_XMLNS_LOG_DIR, log_file_name)

    call_command('fix_xforms_with_undefined_xmlns', log_file_path, noinput=True)

    with open(log_file_path, "r") as f:
        stats = get_summary_stats_from_stream(f)

    if any(stats.values()):
        mail_admins_async.delay(
            'Summary of fix_xforms_with_undefined_xmlns',
            json.dumps(stats, sort_keys=True, indent=4, default=json_handler)
        )

    return stats, log_file_path


def get_summary_stats_from_stream(stream):
    summary = {
        # A dictionary like: {
        #   "foo-domain": 7,
        #   "bar-domain": 3,
        # }
        # This is the number of xforms that were not fixed because the corresponding
        # build contains multiple forms that had been fixed by the
        # fix_forms_and_apps_with_missing_xmlns management command
        'not_fixed_multi_match': defaultdict(lambda: 0),
        # This is the number of xforms that were not fixed because the corresponding
        # build contains either 0 or more than 1 forms with a matching name.
        'not_fixed_cant_match': defaultdict(lambda: 0),
        # This is the number of xforms that were not fixed because the corresponding
        # build contains forms that currently have an "undefined" xmlns. This
        # violates the assumption that all apps and builds had been repaired.
        # domain => number_of_forms_with_undefined_xlmns
        'not_fixed_undefined_xmlns': defaultdict(lambda: 0),
        # This is the number of xforms that had their xmlns replaced successfully
        'fixed': defaultdict(lambda: 0),
        'errors': defaultdict(lambda: 0),
        # A dictionary like : {
        #   "foo-domain": {"user1", "user2"}
        # }
        # showing which users are need to update their apps so that they stop
        # submitting forms with "undefined" xmlns.
        'submitting_bad_forms': defaultdict(set),
        'multi_match_builds': set(),
        'cant_match_form_builds': set(),
        # tuples with (domain, build_id)
        'builds_with_undefined_xmlns': set(),
    }

    for line in stream:
        level, event, extras = parse_log_message(line)
        domain = extras.get('domain', '')
        if event == ERROR_SAVING:
            summary['errors'] += 1
        if event in [SET_XMLNS, MULTI_MATCH, FORM_HAS_UNDEFINED_XMLNS, CANT_MATCH]:
            summary['submitting_bad_forms'][domain].add(extras.get('username', ''))
        if event == SET_XMLNS:
            summary['fixed'][domain] += 1
        elif event == MULTI_MATCH:
            summary['not_fixed_multi_match'][domain] += 1
            summary['multi_match_builds'].add((domain, extras.get('build_id', '')))
        elif event == CANT_MATCH:
            summary['not_fixed_cant_match'][domain] += 1
            summary['cant_match_form_builds'].add((domain, extras.get('build_id', '')))
        elif event == FORM_HAS_UNDEFINED_XMLNS:
            summary['not_fixed_undefined_xmlns'][domain] += 1
            summary['builds_with_undefined_xmlns'].add((domain, extras.get('build_id', '')))

    return summary


def pprint_stats(stats, outstream):
    outstream.write("Number of errors: {}\n".format(sum(stats['errors'].values())))
    outstream.write(
        "Number of xforms that we could not fix (multi match): {}\n".format(
            sum(stats['not_fixed_multi_match'].values()))
    )
    outstream.write(
        "Number of xforms that we could not fix (cant match): {}\n".format(
            sum(stats['not_fixed_cant_match'].values())
        )
    )
    outstream.write(
        "Number of xforms that we could not fix (undef xmlns): {}\n".format(
            sum(stats['not_fixed_undefined_xmlns'].values())
        )
    )
    outstream.write("Number of xforms that we fixed: {}\n".format(
        sum(stats['fixed'].values()))
    )
    outstream.write("Domains and users that submitted bad xforms:\n")
    for domain, users in sorted(stats['submitting_bad_forms'].items()):
        outstream.write(
            "    {} ({} fixed, {} not fixed (multi), {} not fixed (cant_match),"
            " {} not fixed (undef xmlns), {} errors)\n".format(
                domain,
                stats['fixed'][domain],
                stats['not_fixed_multi_match'][domain],
                stats['not_fixed_cant_match'][domain],
                stats['not_fixed_undefined_xmlns'][domain],
                stats['errors'][domain],
            )
        )
        for user in sorted(list(users)):
            outstream.write("        {}\n".format(user))


@periodic_task(run_every=crontab(minute=0, hour=0), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def clear_expired_sessions():
    call_command('clearsessions')


def _get_all_domains_that_have_ever_had_subscriptions():
    return Subscription.visible_and_suppressed_objects.values_list('subscriber__domain', flat=True).distinct()


def _is_monday():
    return datetime.utcnow().isoweekday() == 1


def _has_docs(accessor, db_name):
    return bool(list(accessor.get_doc_ids(db_name, limit=1)))


@periodic_task(run_every=crontab(minute=0, hour=0), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def check_for_sql_cases_without_existing_domain():
    missing_domains_with_cases = set()
    for domain in set(_get_all_domains_that_have_ever_had_subscriptions()) - set(Domain.get_all_names()):
        accessor = CaseReindexAccessor(domain=domain, include_deleted=True)
        for db_name in accessor.sql_db_aliases:
            if _has_docs(accessor, db_name):
                missing_domains_with_cases |= {domain}
                break

    if missing_domains_with_cases:
        mail_admins_async.delay(
            'There exist SQL cases belonging to a missing domain',
            six.text_type(missing_domains_with_cases)
        )
    elif _is_monday():
        mail_admins_async.delay(
            'All SQL cases belong to valid domains', ''
        )


@periodic_task(run_every=crontab(minute=0, hour=1), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def check_for_sql_forms_without_existing_domain():
    missing_domains_with_forms = set()
    for domain in set(_get_all_domains_that_have_ever_had_subscriptions()) - set(Domain.get_all_names()):
        accessor = FormReindexAccessor(domain=domain, include_deleted=True)
        for db_name in accessor.sql_db_aliases:
            if _has_docs(accessor, db_name):
                missing_domains_with_forms |= {domain}
                break

    if missing_domains_with_forms:
        mail_admins_async.delay(
            'There exist SQL forms belonging to a missing domain',
            six.text_type(missing_domains_with_forms)
        )
    elif _is_monday():
        mail_admins_async.delay(
            'All SQL forms belong to valid domains', ''
        )


@periodic_task(run_every=crontab(minute=0, hour=0), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def check_for_elasticsearch_data_without_existing_domain():
    issue_found = False
    deleted_domain_names = set(_get_all_domains_that_have_ever_had_subscriptions()) - set(Domain.get_all_names())
    for domain_name in deleted_domain_names:
        for hqESQuery in [AppES, CaseES, CaseSearchES, FormES, GroupES, LedgerES, UserES]:
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
                'Missing domain "%s" has remaining UCR tables' % missing_domain,
                six.text_type(missing_domains_to_tables[missing_domain])
            )
    elif _is_monday():
        mail_admins_async.delay('All UCR tables belong to valid domains', '')


@periodic_task(run_every=crontab(minute=0, hour=16), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def delete_web_user():
    if settings.SERVER_ENVIRONMENT == 'production':
        for username in [
            'create_growth' + '@' + 'outlook.com',
            'growth_analytics' + '@' + 'outlook.com',
        ]:
            web_user = WebUser.get_by_username(username)
            if web_user:
                web_user.delete()
