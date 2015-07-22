import settings


def group_by_domain(domain, include_docs=True, **kwargs):
    from corehq.apps.groups.models import Group
    return Group.view(
        'groups/by_domain',
        key=domain,
        include_docs=include_docs,
        **kwargs
    )


def stale_group_by_domain(domain, include_docs=True, **kwargs):
    return group_by_domain(
        domain,
        include_docs=include_docs,
        stale=settings.COUCH_STALE_QUERY,
        **kwargs
    )


def group_by_name(domain, name, include_docs=True, **kwargs):
    from corehq.apps.groups.models import Group
    return Group.view(
        'groups/by_name',
        key=[domain, name],
        include_docs=include_docs,
        **kwargs
    )


def stale_group_by_name(domain, name, include_docs=True, **kwargs):
    return group_by_name(
        domain,
        name,
        include_docs=include_docs,
        stale=settings.COUCH_STALE_QUERY,
        **kwargs
    )


def refresh_group_views():
    from corehq.apps.groups.models import Group
    Group.view(
        'groups/by_domain',
        include_docs=False,
        limit=1,
    ).fetch()
    Group.view(
        'groups/by_name',
        include_docs=False,
        limit=1,
    ).fetch()
