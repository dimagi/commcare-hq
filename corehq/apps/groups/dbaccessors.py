from __future__ import absolute_import
from __future__ import unicode_literals
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
