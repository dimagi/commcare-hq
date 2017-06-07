import pytz
import uuid
from casexml.apps.case.mock import CaseBlock
from corehq.apps.data_interfaces.models import CaseRuleActionResult, AUTO_UPDATE_XMLNS
from corehq.apps.hqcase.utils import submit_case_blocks, update_case
from corehq.apps.users.util import SYSTEM_USER_ID
from corehq.util.timezones.conversions import ServerTime
from datetime import datetime
from xml.etree import ElementTree


def _create_tech_issue_delegate_for_escalation(tech_issue, owner_id):
    case_id = uuid.uuid4().hex
    caseblock = CaseBlock(
        case_id,
        case_type='tech_issue_delegate',
        create=True,
        update={'change_in_level': '1'},
        user_id=SYSTEM_USER_ID,
        owner_id=owner_id,
        case_name=tech_issue.name,
        index={'parent': (tech_issue.type, tech_issue.case_id, 'child')},
    )
    return submit_case_blocks(
        ElementTree.tostring(caseblock.as_xml()),
        tech_issue.domain,
        xmlns=AUTO_UPDATE_XMLNS,
    )


def _update_tech_issue_for_escalation(case, escalated_ticket_level):
    today = ServerTime(datetime.utcnow()).user_time(pytz.timezone('Asia/Kolkata')).done().date()

    return update_case(
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


def escalate_tech_issue(case, rule):
    if case.type != 'tech_issue':
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

    result = _update_tech_issue_for_escalation(case, escalated_ticket_level)
    rule.log_submission(result[0].form_id)

    result = _create_tech_issue_delegate_for_escalation(case, escalated_location_id)
    rule.log_submission(result[0].form_id)

    return CaseRuleActionResult(num_updates=1)
