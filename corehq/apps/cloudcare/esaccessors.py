from corehq.apps.es import UserES
from corehq.apps.locations.models import SQLLocation


def login_as_user_query(
        domain,
        couch_user,
        search_string,
        limit,
        offset):
    '''
    Takes in various parameters to determine which users to populate the
    Log In As screen.

    :param domain: String domain
    :param couch_user: The CouchUser that is using the Log In As feature
    :param search_string: The query that filters the users returned. Filters based on the
        `search_fields` as well as any fields defined in `user_data_fields`.
    :param limit: The max amount of users returned.
    :param offset: From where to start the query.

    :returns: An EsQuery instance.
    '''
    search_fields = ["base_username", "last_name", "first_name", "phone_numbers"]

    user_es = (
        UserES()
        .domain(domain)
        .start(offset)
        .size(limit)
        .sort('username.exact')
        .search_string_query(search_string, search_fields)
    )

    if not couch_user.has_permission(domain, 'access_all_locations'):
        loc_ids = SQLLocation.objects.accessible_to_user(
            domain, couch_user
        ).location_ids()
        user_es = user_es.location(list(loc_ids))

    if _limit_login_as(couch_user, domain):
        login_as_users = [couch_user.username]
        if couch_user.has_permission(domain, 'access_default_login_as_user'):
            login_as_users.append('default')
        user_es = user_es.login_as_user(login_as_users)
    return user_es.mobile_users()


def _limit_login_as(couch_user, domain):
    return couch_user.has_permission(domain, 'limited_login_as') \
        and not couch_user.has_permission(domain, 'login_as_all_users')
