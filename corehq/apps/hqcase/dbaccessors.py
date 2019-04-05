from __future__ import absolute_import
from __future__ import unicode_literals

from corehq.util.python_compatibility import soft_assert_type_text
from corehq.util.soft_assert.api import soft_assert
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
        soft_assert_type_text(type)
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


def get_cases_in_domain_by_external_id(domain, external_id):
    return CommCareCase.view(
        'cases_by_domain_external_id/view',
        key=[domain, external_id],
        reduce=False,
        include_docs=True,
    ).all()


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
