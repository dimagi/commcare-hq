from casexml.apps.case.models import CommCareCase


def get_number_of_cases_in_domain(domain):
    row = CommCareCase.get_db().view(
        "hqcase/types_by_domain",
        startkey=[domain],
        endkey=[domain, {}],
        reduce=True,
    ).one()
    return row["value"] if row else 0


def get_case_ids_in_domain(domain, type=None):
    type_key = [type] if type else []
    return [res['id'] for res in CommCareCase.get_db().view(
        'hqcase/types_by_domain',
        startkey=[domain] + type_key,
        endkey=[domain] + type_key + [{}],
        reduce=False,
        include_docs=False,
    )]
