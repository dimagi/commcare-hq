from datetime import datetime

from django.utils.text import slugify

from corehq.apps.case_search.const import SPECIAL_CASE_PROPERTIES_MAP
from corehq.apps.data_interfaces.utils import iter_cases_and_run_rules
from corehq.apps.es import queries
from corehq.apps.es.case_search import CaseSearchES, case_property_missing
from corehq.apps.locations.dbaccessors import user_ids_at_locations
from corehq.messaging.util import MessagingRuleProgressHelper

DUPLICATE_LIMIT = 1000
DEDUPE_XMLNS = 'http://commcarehq.org/hq_case_deduplication_rule'


def _get_es_filtered_case_query(domain, case, case_filter_criteria=None):
    # Import here to avoid circular import error
    from corehq.apps.data_interfaces.models import (
        LocationFilterDefinition,
        MatchPropertyDefinition,
    )

    if case_filter_criteria is None:
        case_filter_criteria = []

    query = CaseSearchES().domain(domain).size(DUPLICATE_LIMIT).case_type(case.type)

    def apply_criterion_to_query(query_, definition):
        if isinstance(definition, MatchPropertyDefinition):
            match_type = definition.match_type

            if match_type == MatchPropertyDefinition.MATCH_HAS_NO_VALUE:
                query_ = query_.case_property_missing(definition.property_name)
            elif match_type == MatchPropertyDefinition.MATCH_HAS_VALUE:
                query_ = query_.NOT(case_property_missing(definition.property_name))
            elif match_type == MatchPropertyDefinition.MATCH_EQUAL:
                query_ = query_.case_property_query(
                    definition.property_name,
                    definition.property_value,
                    queries.MUST,
                )
            elif match_type == MatchPropertyDefinition.MATCH_NOT_EQUAL:
                query_ = query_.case_property_query(
                    definition.property_name,
                    definition.property_value,
                    queries.MUST_NOT,
                )
        elif isinstance(definition, LocationFilterDefinition):
            # Get all users owning cases at definition.location_id
            owners_ids = user_ids_at_locations([definition.location_id])
            # Add the definition.location_id for cases which belong to definition.location_id
            owners_ids.append(definition.location_id)

            query_ = query_.owner(owners_ids)

        return query_

    for criterion in case_filter_criteria:
        query = apply_criterion_to_query(query, criterion.definition)

    return query


def case_exists_in_es(
    domain,
    case,
    case_properties,
    include_closed=False,
    match_type="ALL",
    case_filter_criteria=None,
    exclude_copied_cases=True,
):
    es = _get_es_filtered_case_query(domain, case, case_filter_criteria).size(1)

    if not include_closed:
        es = es.is_closed(False)

    if exclude_copied_cases:
        from corehq.apps.hqcase.case_helper import CaseCopier
        es = es.case_property_missing(CaseCopier.COMMCARE_CASE_COPY_PROPERTY_NAME)

    es, _ = add_case_properties_to_query(es, case, case_properties, match_type)

    es = es.case_property_query('@case_id', case.case_id, queries.MUST)

    return es.count() == 1


def find_duplicate_case_ids(
    domain,
    case,
    case_properties,
    include_closed=False,
    match_type="ALL",
    case_filter_criteria=None,
    exclude_copied_cases=True,
    limit=0
):
    if case_filter_criteria is None:
        case_filter_criteria = []

    es = _get_es_filtered_case_query(domain, case, case_filter_criteria=case_filter_criteria)

    if limit:
        es = es.size(limit)

    if not include_closed:
        es = es.is_closed(False)

    if exclude_copied_cases:
        from corehq.apps.hqcase.case_helper import CaseCopier
        es = es.case_property_missing(CaseCopier.COMMCARE_CASE_COPY_PROPERTY_NAME)

    es, at_least_one_property_query = add_case_properties_to_query(es, case, case_properties, match_type)

    if at_least_one_property_query:
        # We need at least one property query otherwise this would return all the cases in the domain
        return es.get_ids()
    else:
        return [case.case_id]


def add_case_properties_to_query(es, case, case_properties, match_type):
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

    return (es, at_least_one_property_query)


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
        CaseDuplicateNew,
    )
    deduplicate_action = CaseDeduplicationActionDefinition.from_rule(rule)
    CaseDuplicate.objects.filter(action=deduplicate_action).delete()
    CaseDuplicateNew.objects.filter(action=deduplicate_action).delete()


def backfill_deduplicate_rule(domain, rule):
    from corehq.apps.data_interfaces.models import (
        AutomaticUpdateRule,
        CaseDeduplicationActionDefinition,
        DomainCaseRuleRun,
    )

    progress_helper = MessagingRuleProgressHelper(rule.pk)
    total_cases_count = CaseSearchES().domain(domain).case_type(rule.case_type).count()
    progress_helper.set_initial_progress()
    progress_helper.set_total_cases_to_be_processed(total_cases_count)
    now = datetime.utcnow()
    try:
        run_record = DomainCaseRuleRun.objects.create(
            domain=domain,
            started_on=now,
            status=DomainCaseRuleRun.STATUS_RUNNING,
            case_type=rule.case_type,
            workflow=AutomaticUpdateRule.WORKFLOW_DEDUPLICATE,
        )
        action = CaseDeduplicationActionDefinition.from_rule(rule)
        case_iterator = AutomaticUpdateRule.iter_cases(
            domain, rule.case_type, include_closed=action.include_closed
        )
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
        rule.last_run = now
        rule.locked_for_editing = False
        rule.save(update_fields=['last_run', 'locked_for_editing'])


def get_dedupe_xmlns(rule):
    name_slug = slugify(rule.name)
    return f"{DEDUPE_XMLNS}__{name_slug}-{rule.case_type}"


def is_dedupe_xmlns(xmlns):
    return xmlns.startswith(DEDUPE_XMLNS)
