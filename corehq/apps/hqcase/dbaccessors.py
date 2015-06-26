from dimagi.utils.chunked import chunked
from dimagi.utils.couch.database import iter_docs, get_db
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


def get_number_of_cases_per_domain():
    return {
        row["key"][0]: row["value"]
        for row in CommCareCase.get_db().view(
            "hqcase/types_by_domain",
            group=True,
            group_level=1,
        ).all()
    }


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


def get_open_case_ids(domain, owner_id):
    """
    Get all open case ids for a given owner
    """
    return _get_case_ids(domain, owner_id, is_closed=False)


def get_closed_case_ids(domain, owner_id):
    """
    Get all closed case ids for a given owner
    """
    return _get_case_ids(domain, owner_id, is_closed=True)


def _get_case_ids(domain, owner_id, is_closed):
    from casexml.apps.case.models import CommCareCase
    if is_closed is None:
        key = [domain, owner_id]
    else:
        key = [domain, owner_id, is_closed]

    return [row['id'] for row in CommCareCase.get_db().view(
        'hqcase/by_owner',
        reduce=False,
        key=key,
    )]


def get_total_case_count():
    """
    Total count of all cases in the database.
    """
    from casexml.apps.case.models import CommCareCase
    results = CommCareCase.get_db().view(
        'hqcase/by_owner',
        reduce=True,
    ).one()
    return results['value'] if results else 0


def get_number_of_cases_in_domain_by_owner(domain, owner_id):
    res = CommCareCase.get_db().view(
        'hqcase/by_owner',
        startkey=[domain, owner_id],
        endkey=[domain, owner_id, {}],
        reduce=True,
    ).one()
    return res['value'] if res else 0


def get_n_case_ids_in_domain_by_owner(domain, owner_id, n,
                                      start_after_case_id=None):
    view_kwargs = {}
    if start_after_case_id:
        view_kwargs['startkey_docid'] = start_after_case_id
        view_kwargs['skip'] = 1

    return [row['id'] for row in CommCareCase.get_db().view(
        "hqcase/by_owner",
        reduce=False,
        startkey=[domain, owner_id, False],
        endkey=[domain, owner_id, False],
        limit=n,
        **view_kwargs
    )]


def iter_lite_cases_json(case_ids, chunksize=100):
    for case_id_chunk in chunked(case_ids, chunksize):
        rows = CommCareCase.get_db().view(
            'case/get_lite',
            keys=case_id_chunk,
            reduce=False,
        )
        for row in rows:
            yield row['value']


def get_lite_case_json(case_id):
    return CommCareCase.get_db().view(
        "case/get_lite",
        key=case_id,
        include_docs=False,
    ).one()


def get_case_properties(domain, case_type=None):
    """
    For a given case type and domain, get all unique existing case properties,
    known and unknown
    """
    key = [domain]
    if case_type:
        key.append(case_type)
    keys = [row['key'] for row in get_db().view(
        'hqcase/all_case_properties',
        startkey=key,
        endkey=key + [{}],
        reduce=True,
        group=True,
        group_level=3,
    )]
    return sorted(set([property_name for _, _, property_name in keys]))


def get_cases_in_domain_by_external_id(domain, external_id):
    return CommCareCase.view(
        'hqcase/by_domain_external_id',
        key=[domain, external_id],
        reduce=False,
        include_docs=True,
    ).all()


def get_one_case_in_domain_by_external_id(domain, external_id):
    return CommCareCase.view(
        'hqcase/by_domain_external_id',
        key=[domain, external_id],
        reduce=False,
        include_docs=True,
        # limit for efficiency, 2 instead of 1 so it raises if multiple found
        limit=2,
    ).one()


def get_supply_point_case_in_domain_by_id(
        domain, supply_point_integer_id):
    from corehq.apps.commtrack.models import SupplyPointCase
    return SupplyPointCase.view(
        'hqcase/by_domain_external_id',
        key=[domain, str(supply_point_integer_id)],
        reduce=False,
        include_docs=True,
        limit=1,
    ).first()


def get_all_case_owner_ids(domain):
    """
    Get all owner ids that are assigned to cases in a domain.
    """
    from casexml.apps.case.models import CommCareCase
    key = [domain]
    submitted = CommCareCase.get_db().view(
        'hqcase/by_owner',
        group_level=2,
        startkey=key,
        endkey=key + [{}],
    ).all()
    return set([row['key'][1] for row in submitted])
