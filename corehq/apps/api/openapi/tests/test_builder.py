from openapi_spec_validator import validate

from corehq.apps.api.openapi.builder import (
    OPENAPI_VERSION,
    _merge_tags,
    build_all,
    build_document,
)
from corehq.apps.api.openapi.catalogue import ApiEntry, documented_entries
from corehq.apps.api.openapi.operations import resource_paths
from corehq.apps.api.resources import v0_5


def _user_v1_paths():
    entry = ApiEntry(v0_5.CommCareUserResource, 'v1', 'user-v1')
    return resource_paths(entry)


def test_document_shape():
    doc = build_document(_user_v1_paths(), title='Mobile Workers')
    assert doc['openapi'] == OPENAPI_VERSION == '3.0.3'
    assert doc['info']['title'] == 'Mobile Workers'
    assert doc['servers'][0]['url']
    assert '/a/{domain}/api/user/v1/' in doc['paths']
    assert 'PaginationMeta' in doc['components']['schemas']
    assert doc['components']['securitySchemes']
    assert doc['security']


def test_pagination_meta_is_referenced_and_defined():
    doc = build_document(_user_v1_paths(), title='Mobile Workers')
    meta = doc['components']['schemas']['PaginationMeta']
    assert set(meta['properties']) == {
        'limit',
        'offset',
        'total_count',
        'next',
        'previous',
    }


def test_document_validates_against_openapi_30():
    doc = build_document(_user_v1_paths(), title='Mobile Workers')
    validate(doc)


def test_schemas_are_derived_from_the_final_paths_not_an_empty_one():
    """build_document() must compute components.schemas from the paths
    it is actually given -- not from an empty paths that the paths are
    substituted into afterward -- or a schema referenced only by a path
    added post-hoc would silently produce a dangling $ref."""
    paths = _user_v1_paths()
    assert 'PaginationMeta' in build_document(
        paths, title='Mobile Workers'
    )['components']['schemas']
    assert 'PaginationMeta' not in build_document(
        {}, title='Empty'
    )['components']['schemas']


def test_build_all_produces_a_document_per_slug_plus_a_bundle():
    documents = build_all()
    slugs = {entry.doc_slug for entry in documented_entries()}
    # Task 13 adds view-based documents (case-v2), so this is a subset
    # relationship rather than equality.
    assert slugs | {'bundle'} <= set(documents)


def test_every_generated_document_validates():
    for name, doc in build_all().items():
        try:
            validate(doc)
        except Exception as exc:
            raise AssertionError(f'{name} is not valid OpenAPI: {exc}')


def test_bundle_contains_every_documented_path():
    documents = build_all()
    bundle_paths = set(documents['bundle']['paths'])
    for slug, doc in documents.items():
        if slug == 'bundle':
            continue
        assert set(doc['paths']) <= bundle_paths


def test_case_api_v2_is_in_the_generated_documents():
    documents = build_all()
    assert 'case-v2' in documents
    validate(documents['case-v2'])
    paths = documents['case-v2']['paths']
    assert '/a/{domain}/api/case/v2/' in paths
    assert 'requestBody' in paths['/a/{domain}/api/case/v2/']['post']


def test_case_api_v2_covers_all_four_routed_endpoints_with_unique_operation_ids():
    documents = build_all()
    paths = documents['case-v2']['paths']
    assert set(paths) == {
        '/a/{domain}/api/case/v2/',
        '/a/{domain}/api/case/v2/{case_id}/',
        '/a/{domain}/api/case/v2/ext/{external_id}/',
        '/a/{domain}/api/case/v2/bulk-fetch/',
    }
    operation_ids = [
        op['operationId']
        for item in paths.values()
        for method, op in item.items()
        if method != 'parameters'
    ]
    assert len(operation_ids) == len(set(operation_ids))
    # Every GET is body-less; every POST/PUT declares one.
    for path, item in paths.items():
        for method, op in item.items():
            if method == 'parameters':
                continue
            if method == 'get':
                assert 'requestBody' not in op
            else:
                assert 'requestBody' in op, f'{method} {path} has no body'


def test_shared_slug_document_merges_tag_descriptions_from_every_view():
    """case_api and case_api_bulk_fetch share the 'case-v2' doc_slug;
    assert the real per-slug document's own tags -- not just the
    bundle's -- carry a real description."""
    documents = build_all()
    tags = {tag['name']: tag for tag in documents['case-v2']['tags']}
    assert tags['case-v2']['description']


def test_grouping_view_docs_by_slug_keeps_every_views_tag_and_paths():
    """Building the per-slug document from only the first-registered
    view's tag and paths (the old approach) would drop a later view's
    description if the first one had none, and would derive
    components.schemas from an incomplete paths. Two synthetic
    ApiViewDocs sharing a slug -- the first with no description --
    must both contribute."""
    from corehq.apps.api.openapi.builder import _group_view_docs_by_slug
    from corehq.apps.api.openapi.view_adapter import ApiViewDocs

    first = ApiViewDocs(
        summary='',
        description='',
        paths=['/a/{domain}/api/shared/v1/'],
        doc_slug='shared-v1',
    )
    second = ApiViewDocs(
        summary='Second',
        description='The real description.',
        paths=['/a/{domain}/api/shared/v1/other/'],
        doc_slug='shared-v1',
    )
    paths_by_slug, tag_pairs_by_slug = _group_view_docs_by_slug(
        [first, second]
    )
    assert set(paths_by_slug['shared-v1']) == {
        '/a/{domain}/api/shared/v1/',
        '/a/{domain}/api/shared/v1/other/',
    }
    merged = _merge_tags(tag_pairs_by_slug['shared-v1'])
    assert merged == [
        {'name': 'shared-v1', 'description': 'The real description.'}
    ]


def test_case_api_bulk_fetch_document_has_its_own_title_from_the_slug():
    documents = build_all()
    # The merged document's title is derived from the shared doc_slug,
    # not from whichever view registered first (`case_api`'s own
    # summary is 'Cases', not 'Case V2').
    assert documents['case-v2']['info']['title'] == 'Case V2'
