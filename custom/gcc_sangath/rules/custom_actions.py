from corehq.apps.data_interfaces.models import (
    AUTO_UPDATE_XMLNS,
    CaseRuleActionResult,
)
from corehq.apps.hqcase.utils import update_case
from custom.gcc_sangath.const import SESSION_CASE_TYPE


def sanitize_session_peer_rating(session_case, rule):
    """
    For any session case
    sanitize the peer_rating metrics based on child cases of type peer_rating
    """
    if session_case.type != SESSION_CASE_TYPE:
        return CaseRuleActionResult()

    peer_rating_cases = _get_peer_rating_cases(session_case)
    num_updates = 0

    if peer_rating_cases:
        case_updates = _get_case_updates(peer_rating_cases)
        if case_updates:
            (submission, cases) = update_case(
                session_case.domain,
                session_case.case_id,
                case_properties=case_updates,
                xmlns=AUTO_UPDATE_XMLNS,
                device_id=__name__ + ".sanitize_session_peer_rating",
            )
            num_updates = 1
            rule.log_submission(submission.form_id)

    return CaseRuleActionResult(
        num_updates=num_updates,
    )


def _get_peer_rating_cases(session_case):
    # ToDo: fetch peer rating cases
    return []


def _get_case_updates(peer_rating_cases):
    case_updates = {}
    # ToDo: formulate case updates
    return case_updates
