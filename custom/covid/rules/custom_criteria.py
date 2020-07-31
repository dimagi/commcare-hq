from corehq.apps.es.case_search import CaseSearchES, flatten_result
from casexml.apps.case.models import CommCareCase
from corehq.apps.app_manager.const import USERCASE_TYPE


def associated_user_case_closed(case, now):
    if case.closed:
        return False

    if case.type != "checkin":
        return False

    usercase = get_usercase_from_checkin(case)

    if usercase is None:
        return False

    if case.domain != usercase.domain:
        return False

    if usercase.closed:
        return True

    return False


def get_usercase_from_checkin(checkin_case):
    username = checkin_case.get_case_property("username")
    query = (
        CaseSearchES()
        .domain(checkin_case.domain)
        .case_type(USERCASE_TYPE)
        .case_property_query("username", username)
    )

    results = query.run().hits
    if not results:
        return None

    return CommCareCase.wrap(flatten_result(results[0]))
