from __future__ import absolute_import
from __future__ import unicode_literals
import pytz
import uuid
from casexml.apps.case.mock import CaseBlock
from corehq.apps.data_interfaces.models import CaseRuleActionResult, AUTO_UPDATE_XMLNS
from corehq.apps.hqcase.utils import submit_case_blocks, update_case
from corehq.apps.users.util import SYSTEM_USER_ID
from corehq.util.timezones.conversions import ServerTime
from datetime import datetime
from xml.etree import cElementTree as ElementTree


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
        ElementTree.tostring(caseblock.as_xml()).decode('utf-8'),
        tech_issue.domain,
        user_id=SYSTEM_USER_ID,
        xmlns=AUTO_UPDATE_XMLNS,
        device_id=__name__ + "._create_tech_issue_delegate_for_escalation",
    )


def _update_existing_tech_issue_delegate(tech_issue_delegate):
    if tech_issue_delegate.get_case_property('change_in_level') == '1':
        change_in_level = '2'
    else:
        change_in_level = '1'

    return update_case(
        tech_issue_delegate.domain,
        tech_issue_delegate.case_id,
        case_properties={'change_in_level': change_in_level},
        close=False,
        xmlns=AUTO_UPDATE_XMLNS,
        device_id=__name__ + "._update_existing_tech_issue_delegate",
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
        device_id=__name__ + "._update_tech_issue_for_escalation",
    )


def _get_escalated_tech_issue_delegate(tech_issue, escalated_location_id):
    for subcase in tech_issue.get_subcases(index_identifier='parent'):
        if (
            subcase.type == 'tech_issue_delegate' and
            subcase.owner_id == escalated_location_id and
            not subcase.closed
        ):
            return subcase

    return None


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

    update_result = _update_tech_issue_for_escalation(case, escalated_ticket_level)
    rule.log_submission(update_result[0].form_id)

    num_creates = 0
    num_related_updates = 0
    tech_issue_delegate = _get_escalated_tech_issue_delegate(case, escalated_location_id)

    if tech_issue_delegate:
        delegate_update_result = _update_existing_tech_issue_delegate(tech_issue_delegate)
        rule.log_submission(delegate_update_result[0].form_id)
        num_related_updates = 1
    else:
        create_result = _create_tech_issue_delegate_for_escalation(case, escalated_location_id)
        rule.log_submission(create_result[0].form_id)
        num_creates = 1

    return CaseRuleActionResult(num_updates=1, num_creates=num_creates, num_related_updates=num_related_updates)
