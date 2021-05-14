from corehq.apps.es.case_search import CaseSearchES, flatten_result
from casexml.apps.case.models import CommCareCase
from corehq.apps.es.cases import case_type
from corehq.apps.data_interfaces.models import CaseRuleActionResult, AUTO_UPDATE_XMLNS
from corehq.apps.hqcase.utils import update_case
from corehq.apps.es import filters


def close_cases_assigned_to_checkin(checkin_case, rule):
    """
    For any associated checkin case that matches the rule criteria, the following occurs:

    1. For all cases of type [x] find all fields where [assigned_to_primary_checkin_case_id] is set
           to the case ID of the associated checkin case. These are the assigned cases.

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
    for assigned_case in _get_assigned_cases(checkin_case):
        num_related_updates += 1
        (submission, cases) = update_case(
            assigned_case.domain,
            assigned_case.case_id,
            case_properties=blank_properties,
            xmlns=AUTO_UPDATE_XMLNS,
            device_id=__name__ + ".close_cases_assigned_to_checkin",
        )
        rule.log_submission(submission.form_id)

    (close_checkin_submission, cases) = update_case(
        checkin_case.domain,
        checkin_case.case_id,
        close=True,
        xmlns=AUTO_UPDATE_XMLNS,
        device_id=__name__ + ".close_cases_assigned_to_checkin",
    )
    rule.log_submission(close_checkin_submission.form_id)

    return CaseRuleActionResult(
        num_closes=1,
        num_related_updates=num_related_updates,
    )


def _get_assigned_cases(checkin_case):
    """
    An assigned case is a case for which all of the following are true:

    - Case type patient or contact
    - Exists in the same domain as the user case
    - The case property assigned_to_primary_checkin_case_id equals an associated checkin case's case_id

    """

    query = (
        CaseSearchES()
        .domain(checkin_case.domain)
        .filter(filters.OR(case_type("patient"), case_type("contact")))
        .case_property_query("assigned_to_primary_checkin_case_id", checkin_case.case_id)
    )

    return [CommCareCase.wrap(flatten_result(hit)) for hit in query.run().hits]
