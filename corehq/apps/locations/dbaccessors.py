from itertools import imap
from dimagi.utils.couch.database import iter_docs


def _cc_users_by_location(domain, location_id, include_docs=True, wrap=True):
    from corehq.apps.users.models import CommCareUser
    view = CommCareUser.view if wrap else CommCareUser.get_db().view
    return view(
        'locations/users_by_location_id',
        startkey=[domain, location_id, CommCareUser.__name__],
        endkey=[domain, location_id, CommCareUser.__name__, {}],
        include_docs=include_docs,
        reduce=False,
    )


def get_users_by_location_id(domain, location_id):
    """
    Get all mobile_workers for a given location
    """
    return _cc_users_by_location(domain, location_id)


def get_user_docs_by_location(domain, location_id):
    return _cc_users_by_location(domain, location_id, wrap=False).all()


def get_user_ids_by_location(domain, location_id):
    return [user['id'] for user in
            _cc_users_by_location(domain, location_id, include_docs=False)]


def get_one_user_at_location(domain, location_id):
    return _cc_users_by_location(domain, location_id).first()


def get_all_users_by_location(domain, location_id):
    from corehq.apps.users.models import CouchUser
    results = CouchUser.get_db().view(
        'locations/users_by_location_id',
        startkey=[domain, location_id],
        endkey=[domain, location_id, {}],
        include_docs=True,
        reduce=False,
    )
    return (CouchUser.wrap_correctly(res['doc']) for res in results)


def users_have_locations(domain):
    from corehq.apps.users.models import CouchUser
    return bool(CouchUser.get_db().view(
        'locations/users_by_location_id',
        startkey=[domain],
        endkey=[domain, {}],
        reduce=True,
    ).one())


def get_users_assigned_to_locations(domain):
    from corehq.apps.users.models import CouchUser
    ids = [res['id'] for res in CouchUser.get_db().view(
        'locations/users_by_location_id',
        startkey=[domain],
        endkey=[domain, {}],
        include_docs=False,
        reduce=False,
    )]
    return imap(CouchUser.wrap_correctly, iter_docs(CouchUser.get_db(), ids))
