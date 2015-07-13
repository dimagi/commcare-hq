from dimagi.utils.couch.database import iter_docs


def get_all_commcare_users_by_domain(domain):
    """Returns all CommCareUsers by domain regardless of their active status"""
    from corehq.apps.users.models import CommCareUser
    key = [domain, CommCareUser.__name__]
    ids = [user['id'] for user in CommCareUser.get_db().view(
        'domain/docs',
        startkey=key,
        endkey=key + [{}],
        reduce=False,
        include_docs=False)]

    return [CommCareUser.wrap(user) for user in iter_docs(CommCareUser.get_db(), ids)]
