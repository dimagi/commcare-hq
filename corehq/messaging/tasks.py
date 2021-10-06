from corehq.apps.data_interfaces.models import AutomaticUpdateRule
from corehq.apps.sms import tasks as sms_tasks
from corehq.apps.es import CaseES
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.models import CommCareCaseSQL
from corehq.messaging.scheduling.tasks import delete_schedule_instances_for_cases
from corehq.messaging.scheduling.util import utcnow
from corehq.messaging.util import MessagingRuleProgressHelper
from corehq.sql_db.util import (
    get_db_aliases_for_partitioned_query,
    paginate_query,
    paginate_query_across_partitioned_databases
)
from corehq.util.celery_utils import no_result_task
from corehq.util.metrics.load_counters import case_load_counter
from dimagi.utils.chunked import chunked
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


@no_result_task(serializer='pickle', queue=settings.CELERY_REMINDER_CASE_UPDATE_BULK_QUEUE, acks_late=True,
                default_retry_delay=5 * 60, max_retries=12, bind=True)
def sync_case_for_messaging_rule(self, domain, case_id, rule_id):
    try:
        with CriticalSection([get_sync_key(case_id)], timeout=5 * 60):
            _sync_case_for_messaging_rule(domain, case_id, rule_id)
    except Exception as e:
        self.retry(exc=e)


@no_result_task(serializer='pickle', queue=settings.CELERY_REMINDER_CASE_UPDATE_BULK_QUEUE, acks_late=True)
def sync_case_chunk_for_messaging_rule(domain, case_id_chunk, rule_id):
    for case_id in case_id_chunk:
        try:
            with CriticalSection([get_sync_key(case_id)], timeout=5 * 60):
                _sync_case_for_messaging_rule(domain, case_id, rule_id)
        except Exception:
            sync_case_for_messaging_rule.delay(domain, case_id, rule_id)


def _sync_case_for_messaging(domain, case_id):
    try:
        case = CaseAccessors(domain).get_case(case_id)
        sms_tasks.clear_case_caches(case)
    except CaseNotFound:
        case = None
    case_load_counter("messaging_sync", domain)()
    update_messaging_for_case(domain, case_id, case)
    if case is not None:
        run_auto_update_rules_for_case(case)


def update_messaging_for_case(domain, case_id, case):
    if case is None or case.is_deleted:
        clear_messaging_for_case(domain, case_id)
    elif settings.USE_PHONE_ENTRIES:
        sms_tasks._sync_case_phone_number(case)


def clear_messaging_for_case(domain, case_id):
    sms_tasks.delete_phone_numbers_for_owners([case_id])
    delete_schedule_instances_for_cases(domain, [case_id])


def run_auto_update_rules_for_case(case):
    rules = AutomaticUpdateRule.by_domain_cached(case.domain, AutomaticUpdateRule.WORKFLOW_SCHEDULING)
    rules_by_case_type = AutomaticUpdateRule.organize_rules_by_case_type(rules)
    for rule in rules_by_case_type.get(case.type, []):
        rule.run_rule(case, utcnow())


def _get_cached_rule(domain, rule_id):
    rules = AutomaticUpdateRule.by_domain_cached(domain, AutomaticUpdateRule.WORKFLOW_SCHEDULING)
    rules = [rule for rule in rules if rule.pk == rule_id]
    if len(rules) == 1:
        return rules[0]

    deduplicate_rules = AutomaticUpdateRule.by_domain_cached(domain, AutomaticUpdateRule.WORKFLOW_DEDUPLICATE)
    rules = [rule for rule in deduplicate_rules if rule.pk == rule_id]
    return rules[0] if len(rules) == 1 else None


def _sync_case_for_messaging_rule(domain, case_id, rule_id):
    case_load_counter("messaging_rule_sync", domain)()
    try:
        case = CaseAccessors(domain).get_case(case_id)
    except CaseNotFound:
        clear_messaging_for_case(domain, case_id)
        return
    rule = _get_cached_rule(domain, rule_id)
    if rule:
        rule.run_rule(case, utcnow())
        MessagingRuleProgressHelper(rule_id).increment_current_case_count()


def initiate_rule_run(rule):
    if not rule.active:
        return
    AutomaticUpdateRule.objects.filter(pk=rule.pk).update(locked_for_editing=True)
    transaction.on_commit(lambda: run_messaging_rule.delay(rule.domain, rule.pk))


def paginated_case_ids(domain, case_type, db_alias=None):
    args = [
        CommCareCaseSQL,
        Q(domain=domain, type=case_type, deleted=False)
    ]
    if db_alias:
        fn = paginate_query
        args = [db_alias] + args
    else:
        fn = paginate_query_across_partitioned_databases
    row_generator = fn(*args, values=['case_id'], load_source='run_messaging_rule')
    for row in row_generator:
        yield row[0]


def get_case_ids_for_messaging_rule(domain, case_type):
    return paginated_case_ids(domain, case_type)


@no_result_task(serializer='pickle', queue=settings.CELERY_REMINDER_CASE_UPDATE_BULK_QUEUE)
def set_rule_complete(rule_id):
    AutomaticUpdateRule.objects.filter(pk=rule_id).update(locked_for_editing=False)
    MessagingRuleProgressHelper(rule_id).set_rule_complete()


@no_result_task(serializer='pickle', queue=settings.CELERY_REMINDER_CASE_UPDATE_BULK_QUEUE, acks_late=True,
                soft_time_limit=15 * settings.CELERY_TASK_SOFT_TIME_LIMIT)
def run_messaging_rule(domain, rule_id):
    rule = _get_cached_rule(domain, rule_id)
    if not rule:
        return
    progress_helper = MessagingRuleProgressHelper(rule_id)
    total_cases_count = CaseES().domain(domain).case_type(rule.case_type).count()
    progress_helper.set_total_cases_to_be_processed(total_cases_count)

    db_aliases = get_db_aliases_for_partitioned_query()
    progress_helper.set_initial_progress(shard_count=len(db_aliases))
    for db_alias in db_aliases:
        run_messaging_rule_for_shard.delay(domain, rule_id, db_alias)


@no_result_task(serializer='pickle', queue=settings.CELERY_REMINDER_CASE_UPDATE_BULK_QUEUE, acks_late=True,
                soft_time_limit=15 * settings.CELERY_TASK_SOFT_TIME_LIMIT)
def run_messaging_rule_for_shard(domain, rule_id, db_alias):
    rule = _get_cached_rule(domain, rule_id)
    if not rule:
        return

    chunk_size = getattr(settings, 'MESSAGING_RULE_CASE_CHUNK_SIZE', 100)
    progress_helper = MessagingRuleProgressHelper(rule_id)
    if not progress_helper.is_canceled():
        for case_id_chunk in chunked(paginated_case_ids(domain, rule.case_type, db_alias), chunk_size):
            sync_case_chunk_for_messaging_rule.delay(domain, case_id_chunk, rule_id)
            progress_helper.update_total_key_expiry()
            if progress_helper.is_canceled():
                break
    all_shards_complete = progress_helper.mark_shard_complete(db_alias)
    if all_shards_complete:
        # this should get triggered for the last shard
        set_rule_complete.delay(rule_id)
