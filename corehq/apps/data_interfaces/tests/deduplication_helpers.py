from corehq.apps.data_interfaces.models import (
    AutomaticUpdateRule,
    CaseDeduplicationActionDefinition,
    CaseDeduplicationMatchTypeChoices
)


def create_dedupe_rule(name='test-name', case_type='test-case', domain='test-domain'):
    rule = AutomaticUpdateRule.objects.create(
        workflow=AutomaticUpdateRule.WORKFLOW_DEDUPLICATE,
        domain=domain,
        name=name,
        case_type=case_type
    )
    rule.add_action(
        CaseDeduplicationActionDefinition,
        match_type=CaseDeduplicationMatchTypeChoices.ALL,
        case_properties=['prop1'],
        properties_to_update=[]
    )

    return rule
