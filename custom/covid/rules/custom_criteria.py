"""
COVID: Available Criteria
-------------------------

The following criteria can be used in messaging in projects using the ``covid`` custom module.
"""
from corehq.apps.es.case_search import CaseSearchES, case_search_to_case_json
from corehq.apps.app_manager.const import USERCASE_TYPE
from corehq.form_processor.models import CommCareCaseSQL


def associated_usercase_closed(case, now):
    """
    Is this an open checkin case where the associated usercase has been closed?
    """
    if case.closed or case.type != "checkin":
        return False

    usercase = get_usercase_from_checkin(case)
    return (
        usercase is not None
        and case.domain == usercase.domain
        and usercase.closed
    )


def get_usercase_from_checkin(checkin_case):
    username = checkin_case.get_case_property("username")
    if not username:
        return None
    query = (
        CaseSearchES()
        .domain(checkin_case.domain)
        .case_type(USERCASE_TYPE)
        .case_property_query("username", username)
    )

    results = query.run().hits
    if not results:
        return None

    return CommCareCaseSQL(**case_search_to_case_json(results[0]))
