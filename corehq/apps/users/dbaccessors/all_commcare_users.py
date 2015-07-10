def get_all_commcare_users_by_domain(domain):
    """Returns all CommCareUsers by domain regardless of their active status"""
    from corehq.apps.users.models import CommCareUser
    key = [domain, CommCareUser.__name__]

    return [CommCareUser.wrap(user['doc']) for user
            in CommCareUser.get_db().view(
                'domain/docs',
                startkey=key,
                endkey=key + [{}],
                reduce=False,
                include_docs=True)]
