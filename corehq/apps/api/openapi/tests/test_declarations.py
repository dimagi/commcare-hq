from corehq.apps.api.openapi.declarations import query_parameter


def test_query_parameter_defaults_to_an_optional_string():
    assert query_parameter('xmlns', 'Form XML namespace.') == {
        'name': 'xmlns',
        'in': 'query',
        'required': False,
        'description': 'Form XML namespace.',
        'schema': {'type': 'string'},
    }


def test_query_parameter_takes_a_full_schema():
    param = query_parameter(
        'limit', 'How many.', {'type': 'integer', 'default': 20}
    )
    assert param['schema'] == {'type': 'integer', 'default': 20}
    assert param['required'] is False


def test_a_falsy_schema_is_not_mistaken_for_an_omitted_one():
    # `schema or {...}` would silently substitute the default here. An empty
    # schema means "anything", which is a different published contract from
    # "a string".
    assert query_parameter('anything', 'No constraint.', {})['schema'] == {}


def test_a_parameter_with_no_description_omits_the_key():
    # Parameters derived from Meta.filtering have no description -- the
    # filter's own name is all tastypie tells us. An empty description
    # renders as one in the reference pages, so the key is left out.
    assert query_parameter('case_type') == {
        'name': 'case_type',
        'in': 'query',
        'required': False,
        'schema': {'type': 'string'},
    }


def test_an_empty_description_is_omitted_too():
    assert 'description' not in query_parameter('x', '')
