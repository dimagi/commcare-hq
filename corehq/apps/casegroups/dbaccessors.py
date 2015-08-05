from corehq.apps.casegroups.models import CommCareCaseGroup


def get_case_groups_in_domain(domain, limit=None, skip=None):
    extra_kwargs = {}
    if limit is not None:
        extra_kwargs['limit'] = limit
    if skip is not None:
        extra_kwargs['skip'] = skip
    return CommCareCaseGroup.view(
        'casegroups/groups_by_domain',
        startkey=[domain],
        endkey=[domain, {}],
        include_docs=True,
        reduce=False,
        **extra_kwargs
    ).all()


def get_case_group_meta_in_domain(domain):
    """
    returns a list (id, name) tuples sorted by name

    ideal for creating a user-facing dropdown menu, etc.
    """
    return [(r['id'], r['key'][1]) for r in CommCareCaseGroup.view(
        'casegroups/groups_by_domain',
        startkey=[domain],
        endkey=[domain, {}],
        include_docs=False,
        reduce=False,
    ).all()]


def get_number_of_case_groups_in_domain(domain):
    data = CommCareCaseGroup.get_db().view(
        'casegroups/groups_by_domain',
        startkey=[domain],
        endkey=[domain, {}],
        reduce=True
    ).first()
    return data['value'] if data else 0
