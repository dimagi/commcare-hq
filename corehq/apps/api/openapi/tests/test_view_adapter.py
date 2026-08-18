from corehq.apps.api.openapi.view_adapter import VIEW_DOCS, api_docs


def test_decorator_registers_docs_and_returns_the_view():
    @api_docs(
        summary='Test endpoint',
        description='A test endpoint.',
        doc_slug='test-v1',
        paths=['/a/{domain}/api/test/v1/'],
    )
    def view(request, domain):
        return 'called'

    assert view(None, 'demo') == 'called'
    assert view._openapi_docs.summary == 'Test endpoint'
    assert view._openapi_docs.paths == ['/a/{domain}/api/test/v1/']
    assert view._openapi_docs in VIEW_DOCS


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
        FILTER_DESCRIPTIONS,
        SIMPLE_FILTERS,
    )

    filters = {*SIMPLE_FILTERS, *COMPOUND_FILTERS}
    assert filters <= set(FILTER_DESCRIPTIONS), (
        'undocumented Case API filters: '
        f'{sorted(filters - set(FILTER_DESCRIPTIONS))}'
    )


def _case_v2_schema(method, path=None):
    from corehq.apps.hqcase.views import case_api

    schemas = case_api._openapi_docs.request_schemas
    return schemas[(path, method)] if path else schemas[method]


def test_bulk_list_item_schema_has_three_create_branches():
    from corehq.apps.hqcase.views import CASE_LIST_PATH

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
    from corehq.apps.hqcase.views import CASE_EXT_PATH

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
