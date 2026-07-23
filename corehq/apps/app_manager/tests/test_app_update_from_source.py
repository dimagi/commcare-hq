from unittest.mock import MagicMock, patch

import pytest

from couchdbkit.exceptions import ResourceNotFound

from corehq.apps.app_manager.exceptions import AppEditingError
from corehq.apps.app_manager.models.applications import (
    _merge_source_into_app,
    overwrite_app_from_source,
)

APP_MODULE = 'corehq.apps.app_manager.models.applications'


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


@patch(f'{APP_MODULE}._update_valid_domains_for_media')
@patch(f'{APP_MODULE}._update_report_config_ids')
@patch(f'{APP_MODULE}.get_static_report_mapping', return_value={})
@patch(f'{APP_MODULE}.wrap_app')
@patch(f'{APP_MODULE}.get_app')
def test_overwrite_app_from_source_orchestration(
    mock_get_app, mock_wrap_app, mock_report_map, mock_update_reports, mock_valid_domains
):
    existing = MagicMock()
    existing.to_json.return_value = _existing()
    mock_get_app.return_value = existing

    wrapped = MagicMock()
    mock_wrap_app.return_value = wrapped

    source = _source()
    result = overwrite_app_from_source(
        'target-domain', 'existing-id', source, {'name': 'Renamed App'}
    )

    # merged json passed to wrap_app preserves identity, replaces content, applies override
    merged = mock_wrap_app.call_args[0][0]
    assert merged['_id'] == 'existing-id'
    assert merged['modules'] == [{'name': 'new module'}]
    assert merged['name'] == 'Renamed App'

    # attachments extracted and cleared before wrapping
    assert source['_attachments'] == {}

    # report configs remapped and the app saved (save_attachments persists + bumps version)
    mock_update_reports.assert_called_once()
    wrapped.save_attachments.assert_called_once()
    assert result is wrapped


@patch(f'{APP_MODULE}.get_app', side_effect=ResourceNotFound())
def test_overwrite_app_from_source_app_not_found(_mock_get_app):
    with pytest.raises(ResourceNotFound):
        overwrite_app_from_source('target-domain', 'missing-id', _source())
