from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.es import filters, queries, UserES
from corehq.apps.locations.models import SQLLocation


def login_as_user_query(
        domain,
        couch_user,
        search_string,
        limit,
        offset,
        user_data_fields=None):
    '''
    Takes in various parameters to determine which users to populate the login as screen.

    :param domain: String domain
    :param couch_user: The CouchUser that is using the Login As feature
    :param search_string: The query that filters the users returned. Filters based on the
        `search_fields` as well as any fields defined in `user_data_fields`.
    :param limit: The max amount of users returned.
    :param offset: From where to start the query.
    :param user_data_fields: A list of custom user data fields that should also be searched
        by the `search_string`

    :returns: An EsQuery instance.
    '''
    search_fields = ["base_username", "last_name", "first_name", "phone_numbers"]

    should_criteria_query = [
        queries.search_string_query(search_string, search_fields),
    ]

    if user_data_fields:
        or_criteria = []
        for field in user_data_fields:
            or_criteria.append(
                filters.AND(
                    filters.term('user_data_es.key', field),
                    filters.term('user_data_es.value', search_string),
                ),
            )

        should_criteria_query.append(
            queries.nested_filter(
                'user_data_es',
                filters.OR(*or_criteria)
            )
        )

    user_es = (
        UserES()
        .domain(domain)
        .start(offset)
        .size(limit)
        .sort('username.exact')
        .set_query(
            queries.BOOL_CLAUSE(
                queries.SHOULD_CLAUSE(
                    should_criteria_query,
                    # It should either match on the search fields like username or it
                    # should match on the custom user data fields. If this were 2, then
                    # it would require the search string to match both on the search fields and
                    # the custom user data fields.
                    minimum_should_match=1,
                ),
            )
        )
    )

    if not couch_user.has_permission(domain, 'access_all_locations'):
        loc_ids = SQLLocation.objects.accessible_to_user(
            domain, couch_user
        ).location_ids()
        user_es = user_es.location(list(loc_ids))

    return user_es.mobile_users()
