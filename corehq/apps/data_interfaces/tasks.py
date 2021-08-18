from datetime import datetime, timedelta
from typing import List, Optional

from django.conf import settings
from django.core.cache import cache
from django.utils.translation import ugettext as _

from celery.schedules import crontab
from celery.task import periodic_task, task
from celery.utils.log import get_task_logger

from dimagi.utils.couch import CriticalSection
from dimagi.utils.logging import notify_error

from corehq.apps.domain.models import Domain
from corehq.apps.domain_migration_flags.api import any_migrations_in_progress
from corehq.form_processor.interfaces.dbaccessors import (
    CaseAccessors,
    FormAccessors,
)
from corehq.motech.repeaters.dbaccessors import (
    get_couch_repeat_record_ids_by_payload_id,
    get_sql_repeat_records_by_payload_id,
    iter_repeat_record_ids_by_repeater,
)
from corehq.motech.repeaters.models import SQLRepeatRecord
from corehq.sql_db.util import get_db_aliases_for_partitioned_query
from corehq.toggles import DISABLE_CASE_UPDATE_RULE_SCHEDULED_TASK
from corehq.util.decorators import serial_task

from .interfaces import FormManagementMode
from .models import (
    AUTO_UPDATE_XMLNS,
    AutomaticUpdateRule,
    CaseRuleActionResult,
    CaseRuleSubmission,
    DomainCaseRuleRun,
)
from .utils import (
    add_cases_to_case_group,
    archive_or_restore_forms,
    operate_on_payloads,
)

logger = get_task_logger('data_interfaces')
ONE_HOUR = 60 * 60
HALT_AFTER = 23 * 60 * 60


def _get_upload_progress_tracker(upload_id):
    def _progress_tracker(current, total):
        cache.set(upload_id, {
            'inProgress': True,
            'current': current,
            'total': total,
        }, ONE_HOUR)
    return _progress_tracker


@task(serializer='pickle', ignore_result=True)
def bulk_upload_cases_to_group(upload_id, domain, case_group_id, cases):
    results = add_cases_to_case_group(
        domain,
        case_group_id,
        cases,
        progress_tracker=_get_upload_progress_tracker(upload_id)
    )
    cache.set(upload_id, results, ONE_HOUR)


@task(serializer='pickle')
def bulk_form_management_async(archive_or_restore, domain, couch_user, form_ids):
    task = bulk_form_management_async
    mode = FormManagementMode(archive_or_restore, validate=True)

    if not form_ids:
        return {'messages': {'errors': [_('No Forms are supplied')]}}

    response = archive_or_restore_forms(domain, couch_user.user_id, couch_user.username, form_ids, mode, task)
    return response


@periodic_task(serializer='pickle',
    run_every=crontab(hour='*', minute=0),
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
    hour_to_run = now.hour if now else datetime.utcnow().hour
    for domain in domains:
        if not any_migrations_in_progress(domain) and not DISABLE_CASE_UPDATE_RULE_SCHEDULED_TASK.enabled(domain):
            domain_obj = Domain.get_by_name(domain)
            if domain_obj.auto_case_update_hour is None:
                domain_hour = settings.RULE_UPDATE_HOUR
            else:
                domain_hour = domain_obj.auto_case_update_hour
            if hour_to_run == domain_hour:
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


@task(serializer='pickle', queue='case_rule_queue')
def run_case_update_rules_for_domain(domain, now=None):
    now = now or datetime.utcnow()

    domain_rules = AutomaticUpdateRule.by_domain(domain, AutomaticUpdateRule.WORKFLOW_CASE_UPDATE)
    all_rule_case_types = set(domain_rules.values_list('case_type', flat=True))

    for case_type in all_rule_case_types:
        run_record = DomainCaseRuleRun.objects.create(
            domain=domain,
            started_on=datetime.utcnow(),
            status=DomainCaseRuleRun.STATUS_RUNNING,
            case_type=case_type
        )

        for db in get_db_aliases_for_partitioned_query():
            run_case_update_rules_for_domain_and_db.delay(domain, now, run_record.pk, case_type, db=db)


@serial_task(
    '{domain}-{case_type}-{db}',
    timeout=36 * 60 * 60,
    max_retries=0,
    queue='case_rule_queue',
)
def run_case_update_rules_for_domain_and_db(domain, now, run_id, case_type, db=None):
    domain_obj = Domain.get_by_name(domain)
    max_allowed_updates = domain_obj.auto_case_update_limit or settings.MAX_RULE_UPDATES_IN_ONE_RUN
    start_run = datetime.utcnow()

    last_migration_check_time = None
    cases_checked = 0
    case_update_result = CaseRuleActionResult()

    all_rules = AutomaticUpdateRule.by_domain(domain, AutomaticUpdateRule.WORKFLOW_CASE_UPDATE)
    rules = list(all_rules.filter(case_type=case_type))

    boundary_date = AutomaticUpdateRule.get_boundary_date(rules, now)
    for case in AutomaticUpdateRule.iter_cases(domain, case_type, boundary_date, db=db):
        migration_in_progress, last_migration_check_time = check_data_migration_in_progress(
            domain,
            last_migration_check_time
        )

        time_elapsed = datetime.utcnow() - start_run
        if (
            time_elapsed.seconds > HALT_AFTER or
            case_update_result.total_updates >= max_allowed_updates or
            migration_in_progress
        ):
            DomainCaseRuleRun.done(run_id, DomainCaseRuleRun.STATUS_HALTED, cases_checked, case_update_result,
                                   db=db)
            notify_error("Halting rule run for domain %s and case type %s." % (domain, case_type))
            return

        case_update_result.add_result(run_rules_for_case(case, rules, now))
        cases_checked += 1

    run = DomainCaseRuleRun.done(run_id, DomainCaseRuleRun.STATUS_FINISHED, cases_checked, case_update_result,
                                 db=db)

    if run.status == DomainCaseRuleRun.STATUS_FINISHED:
        for rule in rules:
            AutomaticUpdateRule.objects.filter(pk=rule.pk).update(last_run=now)


@task(serializer='pickle', queue='background_queue', acks_late=True, ignore_result=True)
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


@periodic_task(run_every=crontab(hour=0, minute=0), queue='case_rule_queue', ignore_result=True)
def delete_old_rule_submission_logs():
    start = datetime.utcnow()
    max_age = start - timedelta(days=90)
    CaseRuleSubmission.objects.filter(created_on__lt=max_age).delete()


@task(serializer='pickle')
def task_operate_on_payloads(
    record_ids: List[str],
    domain: str,
    action,  # type: Literal['resend', 'cancel', 'requeue']  # 3.8+
    use_sql: bool,
):
    return operate_on_payloads(record_ids, domain, action, use_sql,
                               task=task_operate_on_payloads)


@task(serializer='pickle')
def task_generate_ids_and_operate_on_payloads(
    payload_id: Optional[str],
    repeater_id: Optional[str],
    domain: str,
    action,  # type: Literal['resend', 'cancel', 'requeue']  # 3.8+
    use_sql: bool,
) -> dict:
    repeat_record_ids = _get_repeat_record_ids(payload_id, repeater_id, domain,
                                               use_sql)
    return operate_on_payloads(repeat_record_ids, domain, action, use_sql,
                               task=task_generate_ids_and_operate_on_payloads)


def _get_repeat_record_ids(
    payload_id: Optional[str],
    repeater_id: Optional[str],
    domain: str,
    use_sql: bool,
) -> List[str]:
    if not payload_id and not repeater_id:
        return []
    if payload_id:
        if use_sql:
            records = get_sql_repeat_records_by_payload_id(domain, payload_id)
            return [r.id for r in records]
        else:
            return get_couch_repeat_record_ids_by_payload_id(domain, payload_id)
    else:
        if use_sql:
            queryset = SQLRepeatRecord.objects.filter(
                domain=domain,
                repeater_stub__repeater_id=repeater_id,
            )
            return [r['id'] for r in queryset.values('id')]
        else:
            return list(iter_repeat_record_ids_by_repeater(domain, repeater_id))
