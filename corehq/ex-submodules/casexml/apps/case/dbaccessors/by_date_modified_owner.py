from casexml.apps.case.models import CommCareCase


def get_case_ids_modified_with_owner_since(domain, owner_id, reference_date):
    """
    Gets all cases with a specified owner ID that have been modified
    since a particular reference_date.
    """
    return [
        row['id'] for row in CommCareCase.get_db().view(
            'case/by_date_modified_owner',
            startkey=[domain, {}, {}, owner_id, reference_date],
            endkey=[domain, {}, {}, owner_id, reference_date, {}],
            include_docs=False,
            reduce=False
        )
    ]
