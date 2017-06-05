from corehq.apps.data_interfaces.models import CaseRuleActionResult, AUTO_UPDATE_XMLNS
from corehq.apps.hqcase.utils import update_case


def escalate_tech_issue(case, rule):
    if case.type != 'tech_issue'
        return CaseRuleActionResult()

    escalated_ticket_level_map = {
        'supervisor': 'block',
        'block': 'district',
        'district': 'state',
    }

    current_ticket_level = case.get_case_property('ticket_level')
    if current_ticket_level not in escalated_ticket_level_map:
        return CaseRuleActionResult()

    escalated_ticket_level = escalated_ticket_level_map[current_ticket_level]

    result = update_case(
        case.domain,
        case.case_id,
        case_properties={'ticket_level': escalated_ticket_level},
        close=False,
        xmlns=AUTO_UPDATE_XMLNS,
    )
    rule.log_submission(result[0].form_id)
    return CaseRuleActionResult(num_updates=1)
