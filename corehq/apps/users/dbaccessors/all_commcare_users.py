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


def get_user_docs_by_username(usernames):
    from corehq.apps.users.models import CouchUser
    return [res['doc'] for res in CouchUser.get_db().view(
        'users/by_username',
        keys=usernames,
        reduce=False,
        include_docs=True,
    ).all()]
