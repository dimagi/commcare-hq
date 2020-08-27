from corehq.extensions import extension_point, ResultFormat


def customize_emwf_options_user_query(request, domain, user_query):
    for mutator in emwf_options_user_query_mutators(domain):
        user_query = mutator(request, domain, user_query)
    return user_query


@extension_point(result_format=ResultFormat.FLATTEN)
def emwf_options_user_query_mutators(domain):
    """Get functions to mutate the Elasticsearch query for generating the list of users
    for the ``EmwfOptionsController``.

    Parameters:
        * domain: str

    Returns:
        A list of functions that will be called to mutate the query. The functions
        must take the following arguments and return the mutated query:

        * request: Request
        * domain: str
        * query: UserES query object
    """
