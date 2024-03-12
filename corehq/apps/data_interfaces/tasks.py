from datetime import datetime, timedelta
from typing import List, Literal, Optional  # noqa: F401

from django.conf import settings
from django.core.cache import cache
from django.template.loader import render_to_string
from django.utils.translation import gettext as _

from celery.schedules import crontab
from celery.utils.log import get_task_logger

from dimagi.utils.couch import CriticalSection
from soil import DownloadBase

from casexml.apps.case.mock import CaseBlock
from corehq.apps.celery import periodic_task, task
from corehq.apps.domain.models import Domain
from corehq.apps.domain_migration_flags.api import any_migrations_in_progress
from corehq.apps.hqcase.utils import AUTO_UPDATE_XMLNS
from corehq.apps.users.models import CouchUser
from corehq.form_processor.models import XFormInstance
from corehq.apps.case_importer.do_import import SubmitCaseBlockHandler, RowAndCase
from corehq.motech.repeaters.models import SQLRepeatRecord
from corehq.sql_db.util import get_db_aliases_for_partitioned_query
from corehq.toggles import DISABLE_CASE_UPDATE_RULE_SCHEDULED_TASK
from corehq.util.celery_utils import no_result_task
from corehq.util.decorators import serial_task
from corehq.util.log import send_HTML_email

from .deduplication import backfill_deduplicate_rule, reset_deduplicate_rule
from .interfaces import FormManagementMode
from .models import (
    AutomaticUpdateRule,
    CaseDuplicate,
    CaseDuplicateNew,
    CaseRuleSubmission,
    DomainCaseRuleRun,
)
from .utils import (
    add_cases_to_case_group,
    archive_or_restore_forms,
    iter_cases_and_run_rules,
    operate_on_payloads,
    run_rules_for_case,
)

logger = get_task_logger('data_interfaces')
ONE_HOUR = 60 * 60


def _get_upload_progress_tracker(upload_id):
    def _progress_tracker(current, total):
        cache.set(upload_id, {
            'inProgress': True,
            'current': current,
            'total': total,
        }, ONE_HOUR)
    return _progress_tracker


@no_result_task(queue='case_rule_queue', acks_late=True,
                soft_time_limit=15 * settings.CELERY_TASK_SOFT_TIME_LIMIT)
def reset_and_backfill_deduplicate_rule_task(domain, rule_id):
    try:
        rule = AutomaticUpdateRule.objects.get(
            id=rule_id,
            domain=domain,
            workflow=AutomaticUpdateRule.WORKFLOW_DEDUPLICATE,
            active=True,
            deleted=False,
        )
    except AutomaticUpdateRule.DoesNotExist:
        return

    AutomaticUpdateRule.clear_caches(rule.domain, AutomaticUpdateRule.WORKFLOW_DEDUPLICATE)

    reset_deduplicate_rule(rule)
    backfill_deduplicate_rule(domain, rule)


@task(queue='background_queue')
def delete_duplicates_for_cases(case_ids):
    CaseDuplicate.bulk_remove_unique_cases(case_ids)
    CaseDuplicate.remove_duplicates_for_case_ids(case_ids)

    CaseDuplicateNew.remove_duplicates_for_case_ids(case_ids)


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


@periodic_task(
    serializer='pickle',
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
            case_type=case_type,
            workflow=AutomaticUpdateRule.WORKFLOW_CASE_UPDATE,
        )

        for db in get_db_aliases_for_partitioned_query():
            run_case_update_rules_for_domain_and_db.delay(domain, now, run_record.pk, case_type, db=db)


@serial_task(
    '{domain}-{case_type}-{db}',
    timeout=36 * 60 * 60,
    max_retries=0,
    queue='case_rule_queue',
    serializer='pickle',
)
def run_case_update_rules_for_domain_and_db(domain, now, run_id, case_type, db=None):
    rules = list(
        AutomaticUpdateRule.by_domain(domain, AutomaticUpdateRule.WORKFLOW_CASE_UPDATE).filter(case_type=case_type)
    )

    modified_before = AutomaticUpdateRule.get_boundary_date(rules, now)
    iterator = AutomaticUpdateRule.iter_cases(domain, case_type, db=db, modified_lte=modified_before)
    run = iter_cases_and_run_rules(domain, iterator, rules, now, run_id, case_type, db)

    if run.status == DomainCaseRuleRun.STATUS_FINISHED:
        for rule in rules:
            rule.last_run = now
            rule.save(update_fields=['last_run'])


@task(serializer='pickle', queue='background_queue', acks_late=True, ignore_result=True)
def run_case_update_rules_on_save(case):
    key = 'case-update-on-save-case-{case}'.format(case=case.case_id)
    with CriticalSection([key]):
        update_case = True
        if case.xform_ids:
            last_form = XFormInstance.objects.get_form(case.xform_ids[-1], case.domain)
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
    use_sql: bool = True,
):
    return operate_on_payloads(record_ids, domain, action, task=task_operate_on_payloads)


@task(serializer='pickle')
def task_generate_ids_and_operate_on_payloads(
    payload_id: Optional[str],
    repeater_id: Optional[str],
    domain: str,
    action,  # type: Literal['resend', 'cancel', 'requeue']  # 3.8+
    use_sql: bool = True,
) -> dict:
    repeat_record_ids = _get_repeat_record_ids(payload_id, repeater_id, domain)
    return operate_on_payloads(repeat_record_ids, domain, action,
                               task=task_generate_ids_and_operate_on_payloads)


def _get_repeat_record_ids(payload_id, repeater_id, domain):
    if payload_id:
        queryset = SQLRepeatRecord.objects.filter(
            domain=domain,
            payload_id=payload_id,
        ).order_by('-registered_at')
    elif repeater_id:
        queryset = SQLRepeatRecord.objects.filter(
            domain=domain,
            repeater__id=repeater_id,
        )
    else:
        return []
    return list(queryset.values_list("id", flat=True))


@task
def bulk_case_reassign_async(domain, user_id, owner_id, download_id, report_url):
    task = bulk_case_reassign_async
    case_ids = DownloadBase.get(download_id).get_content()
    DownloadBase.set_progress(task, 0, len(case_ids))
    user = CouchUser.get_by_user_id(user_id)
    submission_handler = SubmitCaseBlockHandler(
        domain,
        import_results=None,
        case_type=None,
        user=user,
        record_form_callback=None,
        throttle=True,
    )
    for idx, case_id in enumerate(case_ids):
        submission_handler.add_caseblock(
            RowAndCase(idx, CaseBlock(case_id, owner_id=owner_id))
        )
        DownloadBase.set_progress(task, idx, len(case_ids))
    submission_handler.commit_caseblocks()
    DownloadBase.set_progress(task, len(case_ids), len(case_ids))
    result = submission_handler.results.to_json()
    result['success'] = True
    result['case_count'] = len(case_ids)
    result['report_url'] = report_url

    def _send_email():
        context = {
            'case_count': len(case_ids),
            'report_url': report_url,
        }
        text_content = """
        {case_count} cases were reassigned. The list of cases that
        were reassigned are <a href='{report_url}'>here</a>.
        It's possible that in the report the owner_id is not yet
        updated, you can open individual cases and confirm
        the right case owner, the report gets updated with a slight delay.
        """.format(**context)
        send_HTML_email(
            "Reassign Cases Complete on {domain}- CommCare HQ",
            user.get_email(),
            render_to_string("data_interfaces/partials/case_reassign_complete_email.html", context),
            text_content=text_content,
            domain=domain,
            use_domain_gateway=True,
        )

    _send_email()
    return {"messages": result}


@task
def bulk_case_copy_async(domain, user_id, owner_id, download_id, report_url, **kwargs):
    from corehq.apps.hqcase.case_helper import CaseCopier
    task = bulk_case_copy_async
    case_ids = DownloadBase.get(download_id).get_content()
    DownloadBase.set_progress(task, 0, len(case_ids))
    user = CouchUser.get_by_user_id(user_id)

    case_copier = CaseCopier(
        domain,
        to_owner=owner_id,
        censor_data=kwargs.get('sensitive_properties', {}),
    )
    case_copier.copy_cases(case_ids, progress_task=task)

    DownloadBase.set_progress(task, len(case_ids), len(case_ids))
    result = case_copier.submission_handler.results.to_json()
    result['success'] = True
    result['case_count'] = len(case_ids)
    result['report_url'] = report_url

    def _send_email():
        context = {
            'case_count': len(case_ids),
            'report_url': report_url,
        }
        text_content = """
        {case_count} cases were copied. The list of cases that
        were copied are <a href='{report_url}'>here</a>.
        It's possible that in the report the owner_id is not yet
        updated, you can open individual cases and confirm
        the right case owner, the report gets updated with a slight delay.
        """.format(**context)
        send_HTML_email(
            "Copy Cases Complete on {domain}- CommCare HQ",
            user.get_email(),
            render_to_string("data_interfaces/partials/case_copy_complete_email.html", context),
            text_content=text_content,
            domain=domain,
            use_domain_gateway=True,
        )

    _send_email()
    return {"messages": result}
