"""What Case API v2 declares through ``@api_docs``.

Kept apart from ``test_view_declarations.py``, which covers the
``@api_docs`` decorator itself: nothing here asserts anything about the
decorator, and everything asserts what ``hqcase`` declares through it --
which filters are published, under what names, and what shape each write
schema has. Sharing a module would mean a failure in any of it reporting
the decorator's name instead of the API's.

The companion ``test_case_v2_urls.py`` covers the routes; this covers the
documentation those routes are published with.
"""


def test_case_api_is_documented():
    from corehq.apps.hqcase.views import case_api

    docs = case_api._openapi_docs
    assert docs.summary
    assert '/a/{domain}/api/case/v2/' in docs.paths
    assert 'case_type' in {p['name'] for p in docs.parameters}


def test_case_api_declares_request_schemas():
    from corehq.apps.hqcase.views import case_api

    schemas = case_api._openapi_docs.request_schemas
    assert 'post' in schemas
    assert schemas['post']['type'] in ('object', 'array')


def test_every_case_api_filter_has_a_description():
    from corehq.apps.hqcase.api.get_list import (
        COMPOUND_FILTERS,
        SIMPLE_FILTERS,
    )
    from corehq.apps.hqcase.api.openapi_parameters import (
        FILTER_DESCRIPTIONS,
    )

    filters = {*SIMPLE_FILTERS, *COMPOUND_FILTERS}
    assert filters <= set(FILTER_DESCRIPTIONS), (
        'undocumented Case API filters: '
        f'{sorted(filters - set(FILTER_DESCRIPTIONS))}'
    )


def test_missing_filter_description_does_not_raise():
    """filter_parameters() runs at import time (a decorator argument in
    hqcase/views.py); a plain FILTER_DESCRIPTIONS[name] lookup would
    turn a filter added without a description into a KeyError during
    Django app loading. It must degrade to a generic description
    instead."""
    from corehq.apps.hqcase.api.openapi_parameters import (
        _filter_description,
    )

    assert _filter_description('not_a_real_filter')


def test_every_compound_filter_is_classified():
    """Each compound filter must be declared date-qualified or freeform.

    The two kinds spell their qualifier differently -- ``.gte`` versus a
    caller-supplied ``.<name>`` -- so publishing one as the other names
    parameters ``_get_filter()`` rejects. The kind used to be inferred
    from absence: anything not listed as freeform was published with date
    qualifiers, so a new compound filter of a third kind would have been
    documented as four date parameters that do not exist, silently.
    """
    from corehq.apps.hqcase.api.get_list import COMPOUND_FILTERS
    from corehq.apps.hqcase.api.openapi_parameters import (
        DATE_COMPOUND_FILTERS,
        FREEFORM_COMPOUND_FILTERS,
    )

    classified = DATE_COMPOUND_FILTERS | set(FREEFORM_COMPOUND_FILTERS)
    assert classified == set(COMPOUND_FILTERS), (
        'unclassified compound filter(s): '
        f'{sorted(set(COMPOUND_FILTERS) - classified)}; '
        'filters classified but no longer defined: '
        f'{sorted(classified - set(COMPOUND_FILTERS))}'
    )


def test_an_unclassified_compound_filter_is_not_published_as_a_date():
    """The fallback publishes a placeholder rather than inventing date
    qualifiers. It cannot raise: filter_parameters() runs at import time
    as a decorator argument, so a hard failure here would break Django
    app loading rather than fail this test."""
    from corehq.apps.hqcase.api.openapi_parameters import (
        _compound_filter_parameters,
    )

    [parameter] = _compound_filter_parameters('not_a_real_filter')
    assert parameter['name'] == 'not_a_real_filter.<qualifier>'
    assert parameter['description']


def test_compound_filters_are_published_under_usable_names():
    """A compound filter's bare prefix (e.g. ``properties``) is not a
    valid query parameter -- _get_filter() requires a ``.`` in the key --
    so the published parameter list must never contain the bare prefix,
    and date-based compound filters must be published as their concrete
    gt/gte/lt/lte qualifiers."""
    from corehq.apps.hqcase.views import case_api

    names = {p['name'] for p in case_api._openapi_docs.parameters}
    assert not names & {
        'properties', 'indices', 'last_modified', 'server_last_modified',
        'date_opened', 'date_closed', 'indexed_on',
    }
    assert 'properties.<name>' in names
    assert 'indices.<identifier>' in names
    for qualifier in ('gt', 'gte', 'lt', 'lte'):
        assert f'last_modified.{qualifier}' in names


def test_paging_and_field_shaping_parameters_are_published():
    """get_list() supports limit/cursor pagination, an xpath 'query'
    filter, and mutually-exclusive fields/exclude field shaping, none of
    which is a case filter -- they must still be documented, or a client
    generated from the spec cannot page or shape a response at all."""
    from corehq.apps.hqcase.views import case_api

    names = {p['name'] for p in case_api._openapi_docs.parameters}
    for name in ('limit', 'cursor', 'query', 'fields', 'exclude'):
        assert name in names
    assert 'fields.<name>' in names
    assert 'exclude.<name>' in names


def _case_v2_schema(method, path=None):
    from corehq.apps.hqcase.views import case_api

    schemas = case_api._openapi_docs.request_schemas
    return schemas[(path, method)] if path else schemas[method]


def test_bulk_list_item_schema_has_three_create_branches():
    from corehq.apps.api.const import CASE_LIST_PATH

    schema = _case_v2_schema('post', CASE_LIST_PATH)
    array_branch = schema['oneOf'][1]
    assert array_branch['type'] == 'array'
    assert array_branch['maxItems'] == 100

    item_branches = array_branch['items']['oneOf']
    assert len(item_branches) == 3
    by_create_enum = {
        tuple(branch['properties']['create']['enum']): branch
        for branch in item_branches
    }
    assert set(by_create_enum) == {(True,), (False,), (None,)}

    create_branch = by_create_enum[(True,)]
    assert set(create_branch['required']) == {
        'create',
        'case_name',
        'case_type',
        'owner_id',
    }

    update_branch = by_create_enum[(False,)]
    assert update_branch['required'] == ['create']
    assert 'case_id' not in update_branch['required']
    assert 'external_id' not in update_branch['required']

    upsert_branch = by_create_enum[(None,)]
    assert set(upsert_branch['required']) == {'create', 'external_id'}
    assert 'case_id' not in upsert_branch['properties']


def test_ext_put_is_an_anyof_of_creation_and_update_schemas():
    from corehq.apps.api.const import CASE_EXT_PATH

    schema = _case_v2_schema('put', CASE_EXT_PATH)
    # Must be anyOf, not oneOf: the client doesn't know in advance
    # whether the case exists, and a creation payload (which has
    # case_name/case_type/owner_id) also legitimately satisfies the
    # update branch (which requires nothing) -- oneOf's "exactly one"
    # rule would wrongly reject that payload as ambiguous.
    assert 'oneOf' not in schema
    assert 'anyOf' in schema
    creation_schema, update_schema = schema['anyOf']
    assert set(creation_schema['required']) == {
        'case_name',
        'case_type',
        'owner_id',
    }
    assert not update_schema.get('required')
