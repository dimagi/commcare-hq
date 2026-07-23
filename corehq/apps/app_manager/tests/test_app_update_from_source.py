import pytest

from corehq.apps.app_manager.exceptions import AppEditingError
from corehq.apps.app_manager.models.applications import _merge_source_into_app


def _existing():
    return {
        'doc_type': 'Application',
        '_id': 'existing-id',
        '_rev': '3-abc',
        'domain': 'target-domain',
        'version': 7,
        'name': 'Existing App',
        'multimedia_map': {'jr://file/commcare/image/m0.png': {'multimedia_id': 'media-1'}},
        'modules': [{'name': 'old module'}],
    }


def _source():
    return {
        'doc_type': 'Application',
        '_id': 'source-id',
        '_rev': '9-xyz',
        'domain': 'source-domain',
        'version': 42,
        'name': 'Source App',
        'multimedia_map': {},
        'modules': [{'name': 'new module'}],
    }


def test_merge_replaces_content_from_source():
    merged = _merge_source_into_app(_existing(), _source())
    assert merged['modules'] == [{'name': 'new module'}]


def test_merge_preserves_identity_name_and_media():
    merged = _merge_source_into_app(_existing(), _source())
    assert merged['_id'] == 'existing-id'
    assert merged['_rev'] == '3-abc'
    assert merged['domain'] == 'target-domain'
    assert merged['version'] == 7
    assert merged['name'] == 'Existing App'
    assert merged['multimedia_map'] == {'jr://file/commcare/image/m0.png': {'multimedia_id': 'media-1'}}


def test_merge_applies_extra_properties():
    merged = _merge_source_into_app(_existing(), _source(), {'name': 'Renamed App'})
    assert merged['name'] == 'Renamed App'


def test_merge_rejects_incompatible_doc_type():
    source = _source()
    source['doc_type'] = 'RemoteApp'
    with pytest.raises(AppEditingError):
        _merge_source_into_app(_existing(), source)


def test_merge_allows_source_without_doc_type():
    source = _source()
    del source['doc_type']
    merged = _merge_source_into_app(_existing(), source)
    assert merged['doc_type'] == 'Application'
