"""
COVID: Available Actions
------------------------

The following actions can be used in messaging in projects using the ``covid`` custom module.
"""
from datetime import datetime

from corehq.apps.domain.models import Domain
from corehq.apps.es.case_search import CaseSearchES
from corehq.apps.es.cases import case_type
from corehq.apps.data_interfaces.models import CaseRuleActionResult
from corehq.apps.hqcase.utils import update_case, AUTO_UPDATE_XMLNS
from corehq.apps.es import filters


def set_all_activity_complete_date_to_today(case, rule):
    """
    For any case matching the criteria, set the all_activity_complete_date property
    to today's date, in YYYY-MM-DD format, based on the domain's default time zone.
    """
    if case.get_case_property("all_activity_complete_date"):
        return CaseRuleActionResult()

    from dimagi.utils.parsing import ISO_DATE_FORMAT
    domain_obj = Domain.get_by_name(case.domain)
    today = datetime.now(domain_obj.get_default_timezone()).strftime(ISO_DATE_FORMAT)
    (submission, cases) = update_case(
        case.domain,
        case.case_id,
        case_properties={
            "all_activity_complete_date": today,
        },
        xmlns=AUTO_UPDATE_XMLNS,
        device_id=__name__ + ".set_all_activity_complete_date_to_today",
        form_name=rule.name,
    )
    rule.log_submission(submission.form_id)

    return CaseRuleActionResult(
        num_related_updates=1,
    )


def close_cases_assigned_to_checkin(checkin_case, rule):
    """
    For any associated checkin case that matches the rule criteria, the following occurs:

    1. For all cases of a given type, find all assigned cases. \
       An assigned case is a case for which all of the following are true:

       - Case type patient or contact
       - Exists in the same domain as the user case
       - The case property assigned_to_primary_checkin_case_id equals an associated checkin case's case_id

    2. For every assigned case, the following case properties are blanked out (set to ""):

       - assigned_to_primary_checkin_case_id
       - is_assigned_primary
       - assigned_to_primary_name
       - assigned_to_primary_username

    """
    if checkin_case.type != "checkin":
        return CaseRuleActionResult()

    blank_properties = {
        "assigned_to_primary_checkin_case_id": "",
        "is_assigned_primary": "",
        "assigned_to_primary_name": "",
        "assigned_to_primary_username": "",
    }
    num_related_updates = 0
    for assigned_case_domain, assigned_case_id in _get_assigned_cases(checkin_case):
        num_related_updates += 1
        (submission, cases) = update_case(
            assigned_case_domain,
            assigned_case_id,
            case_properties=blank_properties,
            xmlns=AUTO_UPDATE_XMLNS,
            device_id=__name__ + ".close_cases_assigned_to_checkin",
            form_name=rule.name,
        )
        rule.log_submission(submission.form_id)

    (close_checkin_submission, cases) = update_case(
        checkin_case.domain,
        checkin_case.case_id,
        close=True,
        xmlns=AUTO_UPDATE_XMLNS,
        device_id=__name__ + ".close_cases_assigned_to_checkin",
        form_name=rule.name,
    )
    rule.log_submission(close_checkin_submission.form_id)

    return CaseRuleActionResult(
        num_closes=1,
        num_related_updates=num_related_updates,
    )


def _get_assigned_cases(checkin_case):
    return (
        CaseSearchES()
        .domain(checkin_case.domain)
        .filter(filters.OR(case_type("patient"), case_type("contact")))
        .case_property_query("assigned_to_primary_checkin_case_id", checkin_case.case_id)
        .values_list('domain', '_id')
    )
