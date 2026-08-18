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
