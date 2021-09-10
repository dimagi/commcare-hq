from itertools import chain

from dimagi.utils.chunked import chunked
from dimagi.utils.couch.database import iter_docs

from corehq.apps.es import UserES
from corehq.apps.locations.models import SQLLocation


def _cc_users_by_location(domain, location_id, include_docs=True, wrap=True, user_class=None):
    from corehq.apps.users.models import CommCareUser
    user_class = user_class or CommCareUser
    view = user_class.view if wrap else user_class.get_db().view
    return view(
        'users_extra/users_by_location_id',
        startkey=[domain, location_id, user_class.__name__],
        endkey=[domain, location_id, user_class.__name__, {}],
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
        'users_extra/users_by_location_id',
        startkey=[domain, location_id],
        endkey=[domain, location_id, {}],
        include_docs=True,
        reduce=False,
    )
    return (CouchUser.wrap_correctly(res['doc']) for res in results)


def get_users_assigned_to_locations(domain):
    from corehq.apps.users.models import CouchUser
    ids = [res['id'] for res in CouchUser.get_db().view(
        'users_extra/users_by_location_id',
        startkey=[domain],
        endkey=[domain, {}],
        include_docs=False,
        reduce=False,
    )]
    return map(CouchUser.wrap_correctly, iter_docs(CouchUser.get_db(), ids))


def get_web_users_by_location(domain, location_id):
    from corehq.apps.users.models import WebUser
    return _cc_users_by_location(domain, location_id, user_class=WebUser)


def get_commcare_users_by_location(domain, location_id):
    from corehq.apps.users.models import CommCareUser
    return _cc_users_by_location(domain, location_id, user_class=CommCareUser)


def get_one_commcare_user_at_location(domain, location_id):
    return get_commcare_users_by_location(domain, location_id).first()


def get_users_location_ids(domain, user_ids):
    """Get the ids of the locations the users are assigned to"""
    result = (UserES()
              .domain(domain)
              .user_ids(user_ids)
              .non_null('assigned_location_ids')
              .source(['assigned_location_ids'])
              .run())
    location_ids = [r['assigned_location_ids'] for r in result.hits if 'assigned_location_ids' in r]
    return list(chain(*location_ids))


def mobile_user_ids_at_locations(location_ids):
    # this doesn't include web users
    return UserES().location(location_ids).get_ids()


def user_ids_at_locations_and_descendants(location_ids):
    location_ids_and_children = SQLLocation.objects.get_locations_and_children_ids(location_ids)
    return mobile_user_ids_at_locations(location_ids_and_children)


def user_ids_at_accessible_locations(domain_name, user):
    accessible_location_ids = SQLLocation.active_objects.accessible_location_ids(domain_name, user)
    return mobile_user_ids_at_locations(accessible_location_ids)


def get_user_ids_from_assigned_location_ids(domain, location_ids):
    """
    Returns {user_id: [location_id, location_id, ...], ...}
    """
    result = (
        UserES()
        .domain(domain)
        .location(location_ids)
        .non_null('assigned_location_ids')
        .fields(['assigned_location_ids', '_id'])
        .run().hits
    )
    ret = {}
    for r in result:
        if 'assigned_location_ids' in r:
            locs = r['assigned_location_ids']
            if not isinstance(locs, list):
                locs = [r['assigned_location_ids']]
            ret[r['_id']] = locs
    return ret


def get_user_ids_from_primary_location_ids(domain, location_ids):
    """
    Returns {user_id: primary_location_id, ...}
    """
    result = (
        UserES()
        .domain(domain)
        .primary_location(location_ids)
        .non_null('location_id')
        .fields(['location_id', '_id'])
        .run().hits
    )
    ret = {}
    for r in result:
        if 'location_id' in r:
            loc = r['location_id']
            ret[r['_id']] = loc
    return ret


def generate_user_ids_from_primary_location_ids(domain, location_ids):
    """
    Creates a generator for iterating through the user ids of the all the users in the
    given domain whose primary location is given in the list of location_ids.
    """
    for location_ids_chunk in chunked(location_ids, 50):
        for user_id in get_user_ids_from_primary_location_ids(domain, location_ids_chunk).keys():
            yield user_id


def generate_user_ids_from_primary_location_ids_from_couch(domain, location_ids):
    """
    Creates a generator for iterating through the user ids of the all the
    mobile workers in the given domain whose primary location is given in
    the list of location_ids.

    Retrieves the information from couch instead of elasticsearch.
    """
    for location_id in location_ids:
        for user_id in get_user_ids_by_location(domain, location_id):
            yield user_id


def get_location_ids_with_location_type(domain, location_type_code):
    """
    Returns a QuerySet with the location_ids of all the unarchived SQLLocations in the
    given domain whose LocationType's code matches the given location_type_code.
    """
    return SQLLocation.objects.filter(
        domain=domain,
        is_archived=False,
        location_type__code=location_type_code,
    ).values_list('location_id', flat=True)


def get_filtered_locations_count(domain, root_location_id=None, **locations_filters):
    """
    Returns the locations count governed by 'locations_filters', starting from
    'root_location_id'.
    """
    if root_location_id is None:
        queryset = SQLLocation.objects.filter(domain=domain)
    else:
        queryset = SQLLocation.objects.get_locations_and_children([root_location_id])

    return queryset.filter(**locations_filters).count()
