from datetime import datetime

from django.utils.text import slugify

from corehq.apps.case_search.const import SPECIAL_CASE_PROPERTIES_MAP
from corehq.apps.data_interfaces.utils import iter_cases_and_run_rules
from corehq.apps.es import CaseES, queries
from corehq.apps.es.case_search import CaseSearchES
from corehq.messaging.util import MessagingRuleProgressHelper

DUPLICATE_LIMIT = 1000
DEDUPE_XMLNS = 'http://commcarehq.org/hq_case_deduplication_rule'


def find_duplicate_case_ids(domain, case, case_properties, include_closed=False, match_type="ALL"):
    es = CaseSearchES().domain(domain).size(DUPLICATE_LIMIT).case_type(case.type)

    if not include_closed:
        es = es.is_closed(False)

    clause = queries.MUST if match_type == "ALL" else queries.SHOULD
    _case_json = None

    at_least_one_property_query = False

    for case_property_name in case_properties:
        if case_property_name in SPECIAL_CASE_PROPERTIES_MAP:
            if _case_json is None:
                _case_json = case.to_json()
            case_property_value = SPECIAL_CASE_PROPERTIES_MAP[case_property_name].value_getter(_case_json)
        else:
            case_property_value = case.get_case_property(case_property_name)

        if not case_property_value:
            continue

        at_least_one_property_query = True

        es = es.case_property_query(
            case_property_name,
            case_property_value,
            clause
        )

    if at_least_one_property_query:
        # We need at least one property query otherwise this would return all the cases in the domain
        return es.get_ids()
    else:
        return [case.case_id]


def reset_and_backfill_deduplicate_rule(rule):
    from corehq.apps.data_interfaces.models import AutomaticUpdateRule
    from corehq.apps.data_interfaces.tasks import (
        reset_and_backfill_deduplicate_rule_task,
    )

    if not rule.active or rule.deleted:
        return

    if rule.workflow != AutomaticUpdateRule.WORKFLOW_DEDUPLICATE:
        raise ValueError("You can only backfill a rule with workflow DEDUPLICATE")

    rule.locked_for_editing = True
    rule.save()
    reset_and_backfill_deduplicate_rule_task.delay(rule.domain, rule.pk)


def reset_deduplicate_rule(rule):
    """Deletes all case duplicates for this rule
    """
    from corehq.apps.data_interfaces.models import (
        CaseDeduplicationActionDefinition,
        CaseDuplicate,
    )
    deduplicate_action = CaseDeduplicationActionDefinition.from_rule(rule)
    CaseDuplicate.objects.filter(action=deduplicate_action).delete()


def backfill_deduplicate_rule(domain, rule):
    from corehq.apps.data_interfaces.models import (
        AutomaticUpdateRule,
        DomainCaseRuleRun,
    )

    progress_helper = MessagingRuleProgressHelper(rule.pk)
    total_cases_count = CaseES().domain(domain).case_type(rule.case_type).count()
    progress_helper.set_total_cases_to_be_processed(total_cases_count)
    now = datetime.utcnow()
    try:
        run_record = DomainCaseRuleRun.objects.create(
            domain=domain,
            started_on=now,
            status=DomainCaseRuleRun.STATUS_RUNNING,
            case_type=rule.case_type,
        )
        case_iterator = AutomaticUpdateRule.iter_cases(domain, rule.case_type)
        iter_cases_and_run_rules(
            domain,
            case_iterator,
            [rule],
            now,
            run_record.id,
            rule.case_type,
            progress_helper=progress_helper,
        )
    finally:
        progress_helper.set_rule_complete()
        AutomaticUpdateRule.objects.filter(pk=rule.pk).update(
            locked_for_editing=False,
            last_run=now,
        )


def get_dedupe_xmlns(rule):
    name_slug = slugify(rule.name)
    return f"{DEDUPE_XMLNS}__{name_slug}-{rule.case_type}"


def is_dedupe_xmlns(xmlns):
    return xmlns.startswith(DEDUPE_XMLNS)
