"""Tests what Case API v2 declares with ``@api_docs``.

``test_view_declarations.py`` tests the ``@api_docs`` decorator itself.
This module tests what ``hqcase`` declares with it: which filters it
publishes, the parameter names it publishes them under, and the shape of
each write schema. If both sets of tests shared one module, a failure in
either set would be reported under the wrong name.

``test_case_v2_urls.py`` tests the routes. This module tests the
documentation that those routes are published with.
"""

from corehq.apps.api.const import CASE_EXT_PATH, CASE_LIST_PATH
from corehq.apps.hqcase.api.get_list import COMPOUND_FILTERS, SIMPLE_FILTERS
from corehq.apps.hqcase.api.openapi_parameters import (
    DATE_COMPOUND_FILTERS,
    FILTER_DESCRIPTIONS,
    FREEFORM_COMPOUND_FILTERS,
    _compound_filter_parameters,
    _filter_description,
)
from corehq.apps.hqcase.views import case_api


def test_case_api_is_documented():
    docs = case_api._openapi_docs
    assert docs.summary
    assert '/a/{domain}/api/case/v2/' in docs.paths
    assert 'case_type' in {p['name'] for p in docs.parameters}


def test_case_api_declares_request_schemas():
    schemas = case_api._openapi_docs.request_schemas
    assert 'post' in schemas
    assert schemas['post']['type'] in ('object', 'array')


def test_every_case_api_filter_has_a_description():
    filters = {*SIMPLE_FILTERS, *COMPOUND_FILTERS}
    assert filters <= set(FILTER_DESCRIPTIONS), (
        'undocumented Case API filters: '
        f'{sorted(filters - set(FILTER_DESCRIPTIONS))}'
    )


def test_missing_filter_description_does_not_raise():
    # `filter_parameters()` is a decorator argument in `hqcase/views.py`,
    # so it runs while Django is loading its apps. If it looked up
    # `FILTER_DESCRIPTIONS[name]` directly, then a filter added without a
    # description would raise `KeyError` and break app loading. It falls
    # back to a generic description instead.
    assert _filter_description('not_a_real_filter')


def test_every_compound_filter_is_classified():
    # Every compound filter must be declared either date-qualified or
    # freeform. The two kinds are qualified differently:
    #
    # * a date filter takes a fixed qualifier, such as `.gte`
    # * a freeform filter takes whatever qualifier the caller supplies,
    #   written here as `.<name>`
    #
    # Publishing one kind as if it were the other would document
    # parameters that `_get_filter()` rejects.
    #
    # The kind used to be inferred from what was missing: a filter that
    # was not listed as freeform got published with date qualifiers. So a
    # new compound filter that was neither kind would silently have been
    # documented as four date parameters that do not exist.
    classified = DATE_COMPOUND_FILTERS | set(FREEFORM_COMPOUND_FILTERS)
    assert classified == set(COMPOUND_FILTERS), (
        'unclassified compound filter(s): '
        f'{sorted(set(COMPOUND_FILTERS) - classified)}; '
        'filters classified but no longer defined: '
        f'{sorted(classified - set(COMPOUND_FILTERS))}'
    )


def test_an_unclassified_compound_filter_is_not_published_as_a_date():
    # An unclassified compound filter falls back to a placeholder
    # qualifier, instead of date qualifiers that it might not accept. The
    # fallback must not raise: `filter_parameters()` is a decorator
    # argument, so it runs while Django is loading its apps, and an
    # exception there would break app loading instead of failing this
    # test.
    [parameter] = _compound_filter_parameters('not_a_real_filter')
    assert parameter['name'] == 'not_a_real_filter.<qualifier>'
    assert parameter['description']


def test_compound_filters_are_published_under_usable_names():
    # The bare prefix of a compound filter, such as `properties`, is not
    # a valid query parameter, because `_get_filter()` requires the key to
    # contain a `.`. So the published parameter list must leave out the
    # bare prefixes, and it must publish each date-based compound filter
    # with its concrete `gt`, `gte`, `lt` and `lte` qualifiers.
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
    # `get_list()` accepts some query parameters that are not case
    # filters:
    #
    # * `limit` and `cursor`, to page through results
    # * `query`, to filter with an XPath expression
    # * `fields` and `exclude`, which are mutually exclusive, to choose
    #   which fields the response includes
    #
    # These must be documented too. Without them, a client generated from
    # the spec can neither page through results nor choose which fields
    # the response includes.
    names = {p['name'] for p in case_api._openapi_docs.parameters}
    for name in ('limit', 'cursor', 'query', 'fields', 'exclude'):
        assert name in names
    assert 'fields.<name>' in names
    assert 'exclude.<name>' in names


def _case_v2_schema(method, path=None):
    schemas = case_api._openapi_docs.request_schemas
    return schemas[(path, method)] if path else schemas[method]


def test_bulk_list_item_schema_has_three_create_branches():
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
    schema = _case_v2_schema('put', CASE_EXT_PATH)
    # The schema must use `anyOf`, not `oneOf`, because the client does
    # not know in advance whether the case already exists. A payload that
    # creates a case includes `case_name`, `case_type` and `owner_id`, and
    # it also satisfies the update branch, which requires no fields at
    # all. `oneOf` matches exactly one branch, so it would wrongly reject
    # such a payload as ambiguous.
    assert 'oneOf' not in schema
    assert 'anyOf' in schema
    creation_schema, update_schema = schema['anyOf']
    assert set(creation_schema['required']) == {
        'case_name',
        'case_type',
        'owner_id',
    }
    assert not update_schema.get('required')
