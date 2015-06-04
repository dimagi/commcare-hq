from corehq.apps.users.models import CommCareUser


def get_users_by_location_id(location_id):
    """
        Get all users for a given location
    """
    return CommCareUser.view(
        'locations/users_by_location_id',
        startkey=[location_id],
        endkey=[location_id, {}],
        include_docs=True
    ).all()
