from openapi_spec_validator import validate

from corehq.apps.api.openapi.builder import (
    OPENAPI_VERSION,
    build_all,
    build_document,
)
from corehq.apps.api.openapi.catalogue import ApiEntry, documented_entries
from corehq.apps.api.resources import v0_5


def test_document_shape():
    entry = ApiEntry(v0_5.CommCareUserResource, 'v1', 'user-v1')
    doc = build_document([entry], title='Mobile Workers')
    assert doc['openapi'] == OPENAPI_VERSION == '3.0.3'
    assert doc['info']['title'] == 'Mobile Workers'
    assert doc['servers'][0]['url']
    assert '/a/{domain}/api/user/v1/' in doc['paths']
    assert 'PaginationMeta' in doc['components']['schemas']
    assert doc['components']['securitySchemes']
    assert doc['security']


def test_pagination_meta_is_referenced_and_defined():
    doc = build_document(
        [ApiEntry(v0_5.CommCareUserResource, 'v1', 'user-v1')],
        title='Mobile Workers',
    )
    meta = doc['components']['schemas']['PaginationMeta']
    assert set(meta['properties']) == {
        'limit',
        'offset',
        'total_count',
        'next',
        'previous',
    }


def test_document_validates_against_openapi_30():
    doc = build_document(
        [ApiEntry(v0_5.CommCareUserResource, 'v1', 'user-v1')],
        title='Mobile Workers',
    )
    validate(doc)


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
