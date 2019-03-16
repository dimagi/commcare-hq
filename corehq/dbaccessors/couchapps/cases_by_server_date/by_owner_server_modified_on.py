from __future__ import absolute_import
from __future__ import unicode_literals
from casexml.apps.case.models import CommCareCase
from dimagi.utils.parsing import json_format_datetime


def get_case_ids_modified_with_owner_since(domain, owner_id, reference_date, until_date=None):
    """
    Gets all cases with a specified owner ID that have been modified
    since a particular reference_date (using the server's timestamp)
    """
    return [
        row['id'] for row in CommCareCase.get_db().view(
            'cases_by_server_date/by_owner_server_modified_on',
            startkey=[domain, owner_id, json_format_datetime(reference_date)],
            endkey=[domain, owner_id, {} if not until_date else json_format_datetime(until_date)],
            include_docs=False,
            reduce=False
        )
    ]
