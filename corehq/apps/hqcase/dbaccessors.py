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
    if type is None:
        type_keys = [[]]
    elif isinstance(type, (list, tuple)):
        type_keys = [[t] for t in type]
    elif isinstance(type, basestring):
        type_keys = [[type]]
    else:
        raise ValueError(
            "Argument type should be a string, tuple, or None: {!r}"
            .format(type)
        )
    return [
        res['id'] for type_key in type_keys
        for res in CommCareCase.get_db().view(
            'hqcase/types_by_domain',
            startkey=[domain] + type_key,
            endkey=[domain] + type_key + [{}],
            reduce=False,
            include_docs=False,
        )
    ]


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


def get_case_ids_in_domain_by_owner(domain, owner_id=None, owner_id__in=None,
                                    closed=None):
    """
    get case_ids for open, closed, or all cases in a domain
    that belong to an owner_id or list of owner_ids

    domain: required
    owner_id: a single owner_id to filter on
    owner_id__in: a list of owner ids to filter on.
        A case matches if it belongs to any of them.
        You cannot specify both this and owner_id
    closed: True (only closed cases), False (only open cases), or None (all)
    returns a list of case_ids

    """
    assert not (owner_id__in and owner_id)
    assert closed in (True, False, None)
    if closed is None:
        closed_flags = [True, False]
    else:
        closed_flags = [closed]
    if owner_id:
        owner_id__in = [owner_id]
    return [res["id"] for res in CommCareCase.view(
        'hqcase/by_owner',
        keys=[[domain, owner_id, closed_flag]
              for owner_id in owner_id__in
              for closed_flag in closed_flags],
        include_docs=False,
        reduce=False,
    )]
