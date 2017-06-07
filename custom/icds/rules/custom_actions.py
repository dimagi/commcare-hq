import pytz
from corehq.apps.data_interfaces.models import CaseRuleActionResult, AUTO_UPDATE_XMLNS
from corehq.apps.hqcase.utils import update_case
from corehq.util.timezones.conversions import ServerTime
from datetime import datetime


def escalate_tech_issue(case, rule):
    if case.type != 'tech_issue'
        return CaseRuleActionResult()

    escalated_ticket_level_map = {
        'supervisor': 'block',
        'block': 'district',
        'district': 'state',
    }

    escalated_location_id_map = {
        'supervisor': case.get_case_property('block_location_id'),
        'block': case.get_case_property('district_location_id'),
        'district': case.get_case_property('state_location_id'),
    }

    current_ticket_level = case.get_case_property('ticket_level')
    escalated_ticket_level = escalated_ticket_level_map.get(current_ticket_level)
    escalated_location_id = escalated_location_id_map.get(current_ticket_level)

    if not escalated_ticket_level or not escalated_location_id:
        return CaseRuleActionResult()

    today = ServerTime(datetime.utcnow()).user_time(pytz.timezone('Asia/Kolkata')).done().date()

    result = update_case(
        case.domain,
        case.case_id,
        case_properties={
            'ticket_level': escalated_ticket_level,
            'change_in_level': '1',
            'touch_case_date': today.strftime('%Y-%m-%d'),
        },
        close=False,
        xmlns=AUTO_UPDATE_XMLNS,
    )
    rule.log_submission(result[0].form_id)
    return CaseRuleActionResult(num_updates=1)
