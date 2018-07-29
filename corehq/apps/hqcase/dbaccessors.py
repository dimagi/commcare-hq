from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.util.soft_assert.api import soft_assert
from dimagi.utils.chunked import chunked
from dimagi.utils.couch.database import iter_docs
from casexml.apps.case.models import CommCareCase
import six


def get_case_ids_in_domain(domain, type=None):
    if type is None:
        type_keys = [[]]
    elif isinstance(type, (list, tuple)):
        soft_assert('skelly@{}'.format('dimagi.com'))(
            False, 'get_case_ids_in_domain called with typle / list arg for type'
        )
        type_keys = [[t] for t in type]
    elif isinstance(type, six.string_types):
        type_keys = [[type]]
    else:
        raise ValueError(
            "Argument type should be a string, tuple, or None: {!r}"
            .format(type)
        )
    return [
        res['id'] for type_key in type_keys
        for res in CommCareCase.get_db().view(
            'case_types_by_domain/view',
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
        'cases_by_owner/view',
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
        'cases_by_owner/view',
        reduce=False,
        key=key,
    )]


def iter_lite_cases_json(case_ids, chunksize=100):
    for case_id_chunk in chunked(case_ids, chunksize):
        rows = CommCareCase.get_db().view(
            'cases_get_lite/get_lite',
            keys=case_id_chunk,
            reduce=False,
        )
        for row in rows:
            yield row['value']


def get_lite_case_json(case_id):
    return CommCareCase.get_db().view(
        "cases_get_lite/get_lite",
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
    keys = [row['key'] for row in CommCareCase.get_db().view(
        'all_case_properties/view',
        startkey=key,
        endkey=key + [{}],
        reduce=True,
        group=True,
        group_level=3,
    )]
    return sorted(set([property_name for _, _, property_name in keys]))


def get_cases_in_domain_by_external_id(domain, external_id):
    return CommCareCase.view(
        'cases_by_domain_external_id/view',
        key=[domain, external_id],
        reduce=False,
        include_docs=True,
    ).all()


def get_supply_point_case_in_domain_by_id(
        domain, supply_point_integer_id):
    from corehq.apps.commtrack.models import SupplyPointCase
    return SupplyPointCase.view(
        'cases_by_domain_external_id/view',
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
        'cases_by_owner/view',
        group_level=2,
        startkey=key,
        endkey=key + [{}],
    ).all()
    return set([row['key'][1] for row in submitted])


def get_deleted_case_ids_by_owner(owner_id):
    return [r["id"] for r in CommCareCase.get_db().view(
        'deleted_data/deleted_cases_by_user',
        startkey=[owner_id],
        endkey=[owner_id, {}],
        reduce=False,
    )]
