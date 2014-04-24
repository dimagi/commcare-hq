from dimagi.utils.couch.database import get_db
from casexml.apps.case.models import CommCareCase


def match_case(domain, scanner_serial, scan_id, date):
    results = get_db().view(
        'uth/uth_lookup',
        startkey=[domain, scanner_serial, scan_id],
        endkey=[domain, scanner_serial, scan_id, {}],
    ).one()

    return CommCareCase.get(results['value'])
