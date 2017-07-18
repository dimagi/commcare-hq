from collections import defaultdict
from django.conf import settings

from corehq.apps.domain.dbaccessors import (
    get_docs_in_domain_by_class,
    get_doc_ids_in_domain_by_class,
)


def group_by_domain(domain):
    from corehq.apps.groups.models import Group
    return get_docs_in_domain_by_class(domain, Group)


def _group_by_name(domain, name, **kwargs):
    from corehq.apps.groups.models import Group
    return list(Group.view(
        'groups/by_name',
        key=[domain, name],
        **kwargs
    ))


def group_by_name(domain, name, include_docs=True):
    return _group_by_name(
        domain,
        name,
        include_docs=include_docs,
    )


def stale_group_by_name(domain, name, include_docs=True):
    return _group_by_name(
        domain,
        name,
        include_docs=include_docs,
        stale=settings.COUCH_STALE_QUERY,
    )


def refresh_group_views():
    from corehq.apps.groups.models import Group
    for view_name in [
        'groups/by_name',
    ]:
        Group.view(
            view_name,
            include_docs=False,
            limit=1,
        ).fetch()


def get_group_ids_by_domain(domain):
    from corehq.apps.groups.models import Group
    return get_doc_ids_in_domain_by_class(domain, Group)


def get_groups_by_user(domain, user_ids):
    """
    given a list of user_ids, get all the groups they each belong to

    returns a dict {user_id: set(group_ids)}
    raises AssertionError if any of the groups invloved is not in `domain`

    """
    from corehq.apps.groups.models import Group
    groups_by_user = defaultdict(set)
    for row in Group.view('groups/by_user', keys=user_ids):
        assert row['value'][0] == domain
        groups_by_user[row['key']].add(row['id'])
    return dict(groups_by_user)
