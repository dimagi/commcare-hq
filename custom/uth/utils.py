from dimagi.utils.couch.database import get_db
from casexml.apps.case.models import CommCareCase


def all_scan_cases(domain, scanner_serial, scan_id):
    return get_db().view(
        'uth/uth_lookup',
        startkey=[domain, scanner_serial, scan_id],
        endkey=[domain, scanner_serial, scan_id, {}],
    ).all()


def match_case(domain, scanner_serial, scan_id, date=None):
    results = all_scan_cases(domain, scanner_serial, scan_id)

    if results:
        return CommCareCase.get(results[-1]['value'])
    else:
        return None
