

from __future__ import absolute_import
from __future__ import unicode_literals


def get_open_case_ids_in_domain(domain, type=None, owner_id=None):
    from casexml.apps.case.models import CommCareCase
    if owner_id is not None and type is None:
        key = ["open owner", domain, owner_id]
    else:
        key = ["open type owner", domain]
        if type is not None:
            key += [type]
        if owner_id is not None:
            key += [owner_id]

    case_ids = [row['id'] for row in CommCareCase.get_db().view(
        'open_cases/open_cases',
        startkey=key,
        endkey=key + [{}],
        reduce=False,
        include_docs=False
    )]
    return case_ids
