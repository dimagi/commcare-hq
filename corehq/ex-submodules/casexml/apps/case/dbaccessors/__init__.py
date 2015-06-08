from .all_cases import *
from .by_owner import *
from .related import *


def get_cases_by_owner_type_status_date(domain, owner_id, case_type,
                                        status=None, date_range=None):
    """
    Get cases in a domain filtered by a number of different fields:

    domain: required, non-null
    owner_id: required, non-null
    case_type: optional, no filter applied if null
    status: optional, no filter applied if null
    date_range: optional (start, end) tuple, no filter applied if null

    returns case stubs in this format:

    CommCareCase(_id=id, type=type, closed=closed)

    **No other fields or dynamic properties set**:
    only _id, type, and closed are set.

    """
    from casexml.apps.case.models import CommCareCase
    couch_key = [domain, status or {}, case_type or {}, owner_id]

    start_date, end_date = date_range or (None, None)
    start_date_key = [start_date.isoformat()] if start_date else []
    end_date_key = [end_date.isoformat()] if end_date else [{}]

    return CommCareCase.view(
        'case/by_date_modified_owner',
        reduce=False,
        startkey=couch_key + start_date_key,
        endkey=couch_key + end_date_key,
        include_docs=False
    ).all()
