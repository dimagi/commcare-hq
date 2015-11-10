from django.conf import settings


def _group_by_domain(domain, **kwargs):
    from corehq.apps.groups.models import Group
    return list(Group.view(
        'groups/by_domain',
        key=domain,
        **kwargs
    ))


def group_by_domain(domain, include_docs=True):
    return _group_by_domain(
        domain,
        include_docs=include_docs,
    )


def stale_group_by_domain(domain, include_docs=True):
    return _group_by_domain(
        domain,
        include_docs=include_docs,
        stale=settings.COUCH_STALE_QUERY,
    )


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
        'groups/by_domain',
        'groups/by_name',
    ]:
        Group.view(
            view_name,
            include_docs=False,
            limit=1,
        ).fetch()
