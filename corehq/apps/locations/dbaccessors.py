from corehq.apps.users.models import CouchUser, CommCareUser, WebUser


def _cc_users_by_location(location_id, include_docs=True, wrap=True):
    view = CommCareUser.view if wrap else CommCareUser.get_db().view
    return view(
        'locations/users_by_location_id',
        startkey=[location_id, CommCareUser.__name__],
        endkey=[location_id, CommCareUser.__name__, {}],
        include_docs=include_docs,
        reduce=False,
    )


def get_users_by_location_id(location_id):
    """
    Get all users for a given location
    """
    return _cc_users_by_location(location_id)


def get_user_docs_by_location(location_id):
    return _cc_users_by_location(location_id, wrap=False).all()


def get_user_ids_by_location(location_id):
    return [user['id'] for user in
            _cc_users_by_location(location_id, include_docs=False)]


def get_one_user_at_location(location_id):
    return _cc_users_by_location(location_id).first()


def get_all_users_by_location(location_id):
    results = CouchUser.get_db().view(
        'locations/users_by_location_id',
        startkey=[location_id],
        endkey=[location_id, {}],
        include_docs=True,
        reduce=False,
    )
    return (CouchUser.wrap_correctly(res['doc']) for res in results)
