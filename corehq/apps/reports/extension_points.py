from corehq.extensions import extension_point, ResultFormat


def customize_user_query(user, domain, user_query):
    for mutator in user_query_mutators(domain):
        user_query = mutator(user, domain, user_query)
    return user_query


@extension_point(result_format=ResultFormat.FLATTEN)
def user_query_mutators(domain):
    """Get functions to mutate the Elasticsearch query for generating the list of users
    that are not a part of test locations.

    Parameters:
        * domain: str

    Returns:
        A list of functions that will be called to mutate the query. The functions
        must take the following arguments and return the mutated query:

        * user: couch_user
        * domain: str
        * query: UserES query object
    """
