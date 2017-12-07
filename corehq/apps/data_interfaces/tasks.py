from __future__ import absolute_import
from celery.schedules import crontab
from celery.task import task, periodic_task
from celery.utils.log import get_task_logger
from corehq.apps.data_interfaces.models import (
    AutomaticUpdateRule,
    CaseRuleActionResult,
    DomainCaseRuleRun,
    AUTO_UPDATE_XMLNS,
)
from corehq.apps.domain_migration_flags.api import any_migrations_in_progress
from corehq.util.decorators import serial_task
from datetime import datetime, timedelta

from corehq.form_processor.interfaces.dbaccessors import CaseAccessors, FormAccessors
from django.conf import settings
from django.core.cache import cache
from django.template.loader import render_to_string
from django.utils.translation import ugettext as _

from corehq.apps.data_interfaces.utils import add_cases_to_case_group, archive_forms_old, archive_or_restore_forms
from .interfaces import FormManagementMode, BulkFormManagementInterface
from .dispatcher import EditDataInterfaceDispatcher
from corehq.util.log import send_HTML_email
from dimagi.utils.couch import CriticalSection
from dimagi.utils.logging import notify_error
import six


logger = get_task_logger('data_interfaces')
ONE_HOUR = 60 * 60
HALT_AFTER = 23 * 60 * 60


@task(ignore_result=True)
def bulk_upload_cases_to_group(download_id, domain, case_group_id, cases):
    results = add_cases_to_case_group(domain, case_group_id, cases)
    cache.set(download_id, results, ONE_HOUR)


@task(ignore_result=True)
def bulk_archive_forms(domain, couch_user, uploaded_data):
    # archive using Excel-data
    response = archive_forms_old(domain, couch_user.user_id, couch_user.username, uploaded_data)

    for msg in response['success']:
        logger.info("[Data interfaces] %s", msg)
    for msg in response['errors']:
        logger.info("[Data interfaces] %s", msg)

    html_content = render_to_string('data_interfaces/archive_email.html', response)
    send_HTML_email(_('Your archived forms'), couch_user.email, html_content)


@task
def bulk_form_management_async(archive_or_restore, domain, couch_user, form_ids):
    task = bulk_form_management_async
    mode = FormManagementMode(archive_or_restore, validate=True)

    if not form_ids:
        return {'messages': {'errors': [_('No Forms are supplied')]}}

    response = archive_or_restore_forms(domain, couch_user.user_id, couch_user.username, form_ids, mode, task)
    return response


@periodic_task(
    run_every=crontab(hour=0, minute=0),
    queue=settings.CELERY_PERIODIC_QUEUE,
    ignore_result=True
)
def run_case_update_rules(now=None):
    domains = (AutomaticUpdateRule
               .objects
               .filter(active=True, deleted=False, workflow=AutomaticUpdateRule.WORKFLOW_CASE_UPDATE)
               .values_list('domain', flat=True)
               .distinct()
               .order_by('domain'))
    for domain in domains:
        if not any_migrations_in_progress(domain):
            run_case_update_rules_for_domain.delay(domain, now)


def run_rules_for_case(case, rules, now):
    aggregated_result = CaseRuleActionResult()
    last_result = None
    for rule in rules:
        if last_result:
            if (
                last_result.num_updates > 0 or
                last_result.num_related_updates > 0 or
                last_result.num_related_closes > 0
            ):
                case = CaseAccessors(case.domain).get_case(case.case_id)

        last_result = rule.run_rule(case, now)
        aggregated_result.add_result(last_result)
        if last_result.num_closes > 0:
            break

    return aggregated_result


def check_data_migration_in_progress(domain, last_migration_check_time):
    utcnow = datetime.utcnow()
    if last_migration_check_time is None or (utcnow - last_migration_check_time) > timedelta(minutes=1):
        return any_migrations_in_progress(domain), utcnow

    return False, last_migration_check_time


@serial_task(
    '{domain}',
    timeout=36 * 60 * 60,
    max_retries=0,
    queue='background_queue',
)
def run_case_update_rules_for_domain(domain, now=None):
    now = now or datetime.utcnow()
    start_run = datetime.utcnow()
    last_migration_check_time = None
    run_record = DomainCaseRuleRun.objects.create(
        domain=domain,
        started_on=start_run,
        status=DomainCaseRuleRun.STATUS_RUNNING,
    )
    cases_checked = 0
    case_update_result = CaseRuleActionResult()

    all_rules = AutomaticUpdateRule.by_domain(domain, AutomaticUpdateRule.WORKFLOW_CASE_UPDATE)
    rules_by_case_type = AutomaticUpdateRule.organize_rules_by_case_type(all_rules)

    for case_type, rules in six.iteritems(rules_by_case_type):
        boundary_date = AutomaticUpdateRule.get_boundary_date(rules, now)
        case_ids = list(AutomaticUpdateRule.get_case_ids(domain, case_type, boundary_date))

        for case in CaseAccessors(domain).iter_cases(case_ids):
            migration_in_progress, last_migration_check_time = check_data_migration_in_progress(domain,
                last_migration_check_time)

            time_elapsed = datetime.utcnow() - start_run
            if (
                time_elapsed.seconds > HALT_AFTER or
                case_update_result.total_updates >= settings.MAX_RULE_UPDATES_IN_ONE_RUN or
                migration_in_progress
            ):
                run_record.done(DomainCaseRuleRun.STATUS_HALTED, cases_checked, case_update_result)
                notify_error("Halting rule run for domain %s." % domain)
                return

            case_update_result.add_result(run_rules_for_case(case, rules, now))
            cases_checked += 1

        for rule in rules:
            rule.last_run = now
            rule.save()

    run_record.done(DomainCaseRuleRun.STATUS_FINISHED, cases_checked, case_update_result)


@task(queue='background_queue', acks_late=True, ignore_result=True)
def run_case_update_rules_on_save(case):
    key = 'case-update-on-save-case-{case}'.format(case=case.case_id)
    with CriticalSection([key]):
        update_case = True
        if case.xform_ids:
            last_form = FormAccessors(case.domain).get_form(case.xform_ids[-1])
            update_case = last_form.xmlns != AUTO_UPDATE_XMLNS
        if update_case:
            rules = AutomaticUpdateRule.by_domain(case.domain,
                AutomaticUpdateRule.WORKFLOW_CASE_UPDATE).filter(case_type=case.type)
            now = datetime.utcnow()
            run_rules_for_case(case, rules, now)
