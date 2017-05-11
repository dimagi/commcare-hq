from corehq.apps.es import filters, queries, UserES
from corehq.apps.locations.models import SQLLocation


def login_as_user_query(
        domain,
        couch_user,
        search_string,
        limit,
        offset,
        can_access_all_locations=False,
        user_data_fields=None):
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
                    minimum_should_match=1,
                ),
            )
        )
    )

    if not can_access_all_locations:
        loc_ids = SQLLocation.objects.accessible_to_user(
            domain, couch_user
        ).location_ids()
        user_es = user_es.location(list(loc_ids))

    return user_es.mobile_users()
