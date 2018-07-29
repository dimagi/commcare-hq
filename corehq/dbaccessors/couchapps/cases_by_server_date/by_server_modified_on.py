from __future__ import absolute_import
from __future__ import unicode_literals
from casexml.apps.case.models import CommCareCase
from corehq.util.dates import iso_string_to_datetime


def get_last_modified_dates(domain, case_ids):
    """
    Given a list of case IDs, return a dict where the ids are keys and the
    values are the last server modified date of that case.
    """
    keys = [[domain, case_id] for case_id in case_ids]
    return dict([
        (row['id'], iso_string_to_datetime(row['value']))
        for row in CommCareCase.get_db().view(
            'cases_by_server_date/by_server_modified_on',
            keys=keys,
            include_docs=False,
            reduce=False
        )
    ])
