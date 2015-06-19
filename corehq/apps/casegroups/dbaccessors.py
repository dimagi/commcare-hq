from corehq.apps.casegroups.models import CommCareCaseGroup


def get_case_groups_in_domain(domain, limit=None, skip=None, include_docs=True):
    extra_kwargs = {}
    if limit is not None:
        extra_kwargs['limit'] = limit
    if skip is not None:
        extra_kwargs['skip'] = skip
    return CommCareCaseGroup.view(
        'case/groups_by_domain',
        startkey=[domain],
        endkey=[domain, {}],
        include_docs=include_docs,
        reduce=False,
        **extra_kwargs
    ).all()
