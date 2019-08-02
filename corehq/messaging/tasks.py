from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.data_interfaces.models import AutomaticUpdateRule
from corehq.apps.sms import tasks as sms_tasks
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.models import CommCareCaseSQL
from corehq.form_processor.utils import should_use_sql_backend
from corehq.messaging.scheduling.tasks import delete_schedule_instances_for_cases
from corehq.messaging.scheduling.util import utcnow
from corehq.messaging.util import MessagingRuleProgressHelper, use_phone_entries
from corehq.sql_db.util import paginate_query_across_partitioned_databases
from corehq.util.celery_utils import no_result_task
from corehq.util.datadog.utils import case_load_counter
from dimagi.utils.couch import CriticalSection
from django.conf import settings
from django.db.models import Q
from django.db import transaction


def get_sync_key(case_id):
    return 'sync-case-for-messaging-%s' % case_id


@no_result_task(serializer='pickle', queue=settings.CELERY_REMINDER_CASE_UPDATE_QUEUE, acks_late=True,
                default_retry_delay=5 * 60, max_retries=12, bind=True)
def sync_case_for_messaging(self, domain, case_id):
    try:
        with CriticalSection([get_sync_key(case_id)], timeout=5 * 60):
            _sync_case_for_messaging(domain, case_id)
    except Exception as e:
        self.retry(exc=e)


@no_result_task(serializer='pickle', queue=settings.CELERY_REMINDER_CASE_UPDATE_QUEUE, acks_late=True,
                default_retry_delay=5 * 60, max_retries=12, bind=True)
def sync_case_for_messaging_rule(self, domain, case_id, rule_id):
    try:
        with CriticalSection([get_sync_key(case_id)], timeout=5 * 60):
            _sync_case_for_messaging_rule(domain, case_id, rule_id)
    except Exception as e:
        self.retry(exc=e)


def _sync_case_for_messaging(domain, case_id):
    try:
        case = CaseAccessors(domain).get_case(case_id)
        sms_tasks.clear_case_caches(case)
    except CaseNotFound:
        case = None
    case_load_counter("messaging_sync", domain)()

    if case is None or case.is_deleted:
        sms_tasks.delete_phone_numbers_for_owners([case_id])
        delete_schedule_instances_for_cases(domain, [case_id])
        return

    if use_phone_entries():
        sms_tasks._sync_case_phone_number(case)

    rules = AutomaticUpdateRule.by_domain_cached(case.domain, AutomaticUpdateRule.WORKFLOW_SCHEDULING)
    rules_by_case_type = AutomaticUpdateRule.organize_rules_by_case_type(rules)
    for rule in rules_by_case_type.get(case.type, []):
        rule.run_rule(case, utcnow())


def _get_cached_rule(domain, rule_id):
    rules = AutomaticUpdateRule.by_domain_cached(domain, AutomaticUpdateRule.WORKFLOW_SCHEDULING)
    rules = [rule for rule in rules if rule.pk == rule_id]
    return rules[0] if len(rules) == 1 else None


def _sync_case_for_messaging_rule(domain, case_id, rule_id):
    case_load_counter("messaging_rule_sync", domain)()
    case = CaseAccessors(domain).get_case(case_id)
    rule = _get_cached_rule(domain, rule_id)
    if rule:
        rule.run_rule(case, utcnow())
        MessagingRuleProgressHelper(rule_id).increment_current_case_count()


def initiate_messaging_rule_run(rule):
    if not rule.active:
        return
    AutomaticUpdateRule.objects.filter(pk=rule.pk).update(locked_for_editing=True)
    transaction.on_commit(lambda: run_messaging_rule.delay(rule.domain, rule.pk))


def paginated_case_ids(domain, case_type):
    row_generator = paginate_query_across_partitioned_databases(
        CommCareCaseSQL,
        Q(domain=domain, type=case_type, deleted=False),
        values=['case_id'],
        load_source='run_messaging_rule'
    )
    for row in row_generator:
        yield row[0]


def get_case_ids_for_messaging_rule(domain, case_type):
    if not should_use_sql_backend(domain):
        return CaseAccessors(domain).get_case_ids_in_domain(case_type)
    else:
        return paginated_case_ids(domain, case_type)


@no_result_task(serializer='pickle', queue=settings.CELERY_REMINDER_CASE_UPDATE_QUEUE)
def set_rule_complete(rule_id):
    AutomaticUpdateRule.objects.filter(pk=rule_id).update(locked_for_editing=False)
    MessagingRuleProgressHelper(rule_id).set_rule_complete()


@no_result_task(serializer='pickle', queue=settings.CELERY_REMINDER_RULE_QUEUE, acks_late=True)
def run_messaging_rule(domain, rule_id):
    rule = _get_cached_rule(domain, rule_id)
    if not rule:
        return

    incr = 0
    progress_helper = MessagingRuleProgressHelper(rule_id)
    progress_helper.set_initial_progress()

    for case_id in get_case_ids_for_messaging_rule(domain, rule.case_type):
        sync_case_for_messaging_rule.delay(domain, case_id, rule_id)
        incr += 1
        if incr >= 1000:
            progress_helper.increase_total_case_count(incr)
            incr = 0
            if progress_helper.is_canceled():
                break

    progress_helper.increase_total_case_count(incr)

    # By putting this task last in the queue, the rule should be marked
    # complete at about the time that the last tasks are finishing up.
    # This beats saving the task results in the database and using a
    # celery chord which would be more taxing on system resources.
    set_rule_complete.delay(rule_id)
