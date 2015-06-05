from dimagi.utils.couch.database import iter_docs
from casexml.apps.case.models import CommCareCase


def get_number_of_cases_in_domain(domain, type=None):
    type_key = [type] if type else []
    row = CommCareCase.get_db().view(
        "hqcase/types_by_domain",
        startkey=[domain] + type_key,
        endkey=[domain] + type_key + [{}],
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


def get_cases_in_domain(domain, type=None):
    return (CommCareCase.wrap(doc)
            for doc in iter_docs(CommCareCase.get_db(),
                                 get_case_ids_in_domain(domain, type=type)))


def get_case_types_for_domain(domain):
    key = [domain]
    rows = CommCareCase.get_db().view(
        'hqcase/types_by_domain',
        startkey=key,
        endkey=key + [{}],
        group_level=2,
    ).all()
    case_types = []
    for row in rows:
        _, case_type = row['key']
        if case_type:
            case_types.append(case_type)
    return case_types
