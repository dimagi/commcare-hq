from __future__ import absolute_import
from corehq.apps.data_interfaces.models import AutomaticUpdateRule
from corehq.apps.reminders import tasks as reminders_tasks
from corehq.apps.reminders.models import CaseReminderHandler
from corehq.apps.sms import tasks as sms_tasks
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.models import CommCareCaseSQL
from corehq.form_processor.utils import should_use_sql_backend
from corehq.messaging.scheduling.util import utcnow
from corehq.messaging.util import MessagingRuleProgressHelper
from corehq.sql_db.util import run_query_across_partitioned_databases
from corehq.util.celery_utils import no_result_task
from dimagi.utils.couch import CriticalSection
from django.conf import settings
from django.db.models import Q


def get_sync_key(case_id):
    return 'sync-case-for-messaging-%s' % case_id


@no_result_task(queue=settings.CELERY_REMINDER_CASE_UPDATE_QUEUE, acks_late=True,
                default_retry_delay=5 * 60, max_retries=12, bind=True)
def sync_case_for_messaging(self, domain, case_id):
    try:
        with CriticalSection([get_sync_key(case_id)], timeout=5 * 60):
            _sync_case_for_messaging(domain, case_id)
    except Exception as e:
        self.retry(exc=e)


@no_result_task(queue=settings.CELERY_REMINDER_CASE_UPDATE_QUEUE, acks_late=True,
                default_retry_delay=5 * 60, max_retries=12, bind=True)
def sync_case_for_messaging_rule(self, domain, case_id, rule_id):
    try:
        with CriticalSection([get_sync_key(case_id)], timeout=5 * 60):
            _sync_case_for_messaging_rule(domain, case_id, rule_id)
    except Exception as e:
        self.retry(exc=e)


def _sync_case_for_messaging(domain, case_id):
    case = CaseAccessors(domain).get_case(case_id)
    sms_tasks.clear_case_caches(case)

    if settings.SERVER_ENVIRONMENT not in settings.ICDS_ENVS:
        sms_tasks._sync_case_phone_number(case)

    handler_ids = CaseReminderHandler.get_handler_ids_for_case_post_save(case.domain, case.type)
    if handler_ids:
        reminders_tasks._process_case_changed_for_case(domain, case, handler_ids)

    rules = AutomaticUpdateRule.by_domain_cached(case.domain, AutomaticUpdateRule.WORKFLOW_SCHEDULING)
    rules_by_case_type = AutomaticUpdateRule.organize_rules_by_case_type(rules)
    for rule in rules_by_case_type.get(case.type, []):
        rule.run_rule(case, utcnow())


def _get_cached_rule(domain, rule_id):
    rules = AutomaticUpdateRule.by_domain_cached(domain, AutomaticUpdateRule.WORKFLOW_SCHEDULING)
    rules = [rule for rule in rules if rule.pk == rule_id]

    if len(rules) != 1:
        return None

    return rules[0]


def _sync_case_for_messaging_rule(domain, case_id, rule_id):
    case = CaseAccessors(domain).get_case(case_id)
    rule = _get_cached_rule(domain, rule_id)
    if rule:
        rule.run_rule(case, utcnow())
        MessagingRuleProgressHelper(rule_id).increment_current_case_count()


def initiate_messaging_rule_run(domain, rule_id):
    MessagingRuleProgressHelper(rule_id).set_initial_progress()
    AutomaticUpdateRule.objects.filter(pk=rule_id).update(locked_for_editing=True)
    run_messaging_rule.delay(domain, rule_id)


def get_case_ids_for_messaging_rule(domain, case_type):
    if not should_use_sql_backend(domain):
        return CaseAccessors(domain).get_case_ids_in_domain(case_type)
    else:
        return run_query_across_partitioned_databases(
            CommCareCaseSQL,
            Q(domain=domain, type=case_type, deleted=False),
            values=['case_id']
        )


@no_result_task(queue=settings.CELERY_REMINDER_CASE_UPDATE_QUEUE)
def set_rule_complete(rule_id):
    AutomaticUpdateRule.objects.filter(pk=rule_id).update(locked_for_editing=False)
    MessagingRuleProgressHelper(rule_id).set_rule_complete()


@no_result_task(queue=settings.CELERY_REMINDER_RULE_QUEUE, acks_late=True)
def run_messaging_rule(domain, rule_id):
    rule = _get_cached_rule(domain, rule_id)
    if not rule:
        return

    total_count = 0
    progress_helper = MessagingRuleProgressHelper(rule_id)

    for case_id in get_case_ids_for_messaging_rule(domain, rule.case_type):
        sync_case_for_messaging_rule.delay(domain, case_id, rule_id)
        total_count += 1
        if total_count % 1000 == 0:
            progress_helper.set_total_case_count(total_count)

    progress_helper.set_total_case_count(total_count)

    # By putting this task last in the queue, the rule should be marked
    # complete at about the time that the last tasks are finishing up.
    # This beats saving the task results in the database and using a
    # celery chord which would be more taxing on system resources.
    set_rule_complete.delay(rule_id)
