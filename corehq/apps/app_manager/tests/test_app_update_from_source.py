from unittest.mock import MagicMock, patch

import pytest

from couchdbkit.exceptions import ResourceNotFound
from django.test import TestCase

from corehq.apps.app_manager.exceptions import AppEditingError
from corehq.apps.app_manager.models import Application, Module
from corehq.apps.app_manager.models.applications import (
    _merge_source_into_app,
    overwrite_app_from_source,
)
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.userreports.exceptions import ReportConfigurationNotFoundError

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
@patch(f'{APP_MODULE}.get_app_doc')
def test_overwrite_app_from_source_orchestration(
    mock_get_app_doc, mock_wrap_app, mock_report_map, mock_update_reports, mock_valid_domains
):
    mock_get_app_doc.return_value = _existing()

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


@patch(f'{APP_MODULE}.get_app_doc', side_effect=ResourceNotFound())
def test_overwrite_app_from_source_app_not_found(_mock_get_app_doc):
    with pytest.raises(ResourceNotFound):
        overwrite_app_from_source('target-domain', 'missing-id', _source())


@patch(f'{APP_MODULE}._update_valid_domains_for_media')
@patch(f'{APP_MODULE}._update_report_config_ids')
@patch(f'{APP_MODULE}.get_static_report_mapping', return_value={})
@patch(f'{APP_MODULE}.wrap_app')
@patch(f'{APP_MODULE}.get_app_doc')
def test_overwrite_app_from_source_passes_through_attachments(
    mock_get_app_doc, mock_wrap_app, mock_report_map, mock_update_reports, mock_valid_domains
):
    mock_get_app_doc.return_value = _existing()

    wrapped = MagicMock()
    mock_wrap_app.return_value = wrapped

    source = _source()
    source['_attachments'] = {'foo.xml': 'some data'}

    overwrite_app_from_source('target-domain', 'existing-id', source)

    wrapped.save_attachments.assert_called_once_with({'foo.xml': 'some data'})
    assert source['_attachments'] == {}


@patch(f'{APP_MODULE}.messages')
@patch(f'{APP_MODULE}._update_valid_domains_for_media', side_effect=ResourceNotFound())
@patch(f'{APP_MODULE}._update_report_config_ids')
@patch(f'{APP_MODULE}.get_static_report_mapping', return_value={})
@patch(f'{APP_MODULE}.wrap_app')
@patch(f'{APP_MODULE}.get_app_doc')
def test_overwrite_app_from_source_warns_on_missing_multimedia(
    mock_get_app_doc, mock_wrap_app, mock_report_map, mock_update_reports, mock_valid_domains, mock_messages
):
    mock_get_app_doc.return_value = _existing()

    wrapped = MagicMock()
    mock_wrap_app.return_value = wrapped

    request = MagicMock()
    result = overwrite_app_from_source('target-domain', 'existing-id', _source(), request=request)

    mock_messages.warning.assert_called_once()
    assert result is wrapped


@patch(f'{APP_MODULE}.messages')
@patch(f'{APP_MODULE}._update_valid_domains_for_media', side_effect=ReportConfigurationNotFoundError())
@patch(f'{APP_MODULE}._update_report_config_ids')
@patch(f'{APP_MODULE}.get_static_report_mapping', return_value={})
@patch(f'{APP_MODULE}.wrap_app')
@patch(f'{APP_MODULE}.get_app_doc')
def test_overwrite_app_from_source_warns_on_missing_ucr_with_request(
    mock_get_app_doc, mock_wrap_app, mock_report_map, mock_update_reports, mock_valid_domains, mock_messages
):
    mock_get_app_doc.return_value = _existing()

    wrapped = MagicMock()
    mock_wrap_app.return_value = wrapped

    request = MagicMock()
    result = overwrite_app_from_source('target-domain', 'existing-id', _source(), request=request)

    mock_messages.warning.assert_called_once()
    assert result is wrapped


@patch(f'{APP_MODULE}.messages')
@patch(f'{APP_MODULE}._update_valid_domains_for_media', side_effect=ReportConfigurationNotFoundError())
@patch(f'{APP_MODULE}._update_report_config_ids')
@patch(f'{APP_MODULE}.get_static_report_mapping', return_value={})
@patch(f'{APP_MODULE}.wrap_app')
@patch(f'{APP_MODULE}.get_app_doc')
def test_overwrite_app_from_source_swallows_missing_ucr_without_request(
    mock_get_app_doc, mock_wrap_app, mock_report_map, mock_update_reports, mock_valid_domains, mock_messages
):
    mock_get_app_doc.return_value = _existing()

    wrapped = MagicMock()
    mock_wrap_app.return_value = wrapped

    result = overwrite_app_from_source('target-domain', 'existing-id', _source(), request=None)

    mock_messages.warning.assert_not_called()
    assert result is wrapped


class OverwriteAppFromSourceDbTest(TestCase):
    """Live-DB round-trip covering the guarantees the mock-based tests can't:
    the update persists in place at the same ``_id``, bumps the version exactly
    once, replaces content from the source, and preserves the existing app's
    multimedia map instead of taking the source's."""

    domain = 'test-app-update-domain'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        domain = create_domain(cls.domain)
        cls.addClassCleanup(domain.delete)

    def _make_app(self, app_name, module_name):
        app = Application.new_app(self.domain, app_name)
        app.add_module(Module.new_module(module_name, 'en'))
        app.save()
        self.addCleanup(app.delete)
        return app

    def test_update_persists_in_place(self):
        target = self._make_app('Target App', 'OriginalModule')
        target_id = target._id
        original_version = target.version

        source_app = self._make_app('Source App', 'UpdatedModule')
        source = source_app.export_json(dump_json=False)
        # An entry in the source's map must NOT leak onto the updated app;
        # the existing (empty) map is preserved instead.
        source['multimedia_map'] = {
            'jr://file/commcare/image/injected.png': {
                'multimedia_id': 'from-source', 'media_type': 'CommCareImage',
            }
        }

        overwrite_app_from_source(self.domain, target_id, source)

        updated = Application.get(target_id)
        assert updated._id == target_id
        assert updated.version == original_version + 1
        assert updated.get_module(0).name['en'] == 'UpdatedModule'
        assert updated.multimedia_map == {}

    def test_update_can_rename_via_extra_properties(self):
        target = self._make_app('Original Name', 'OriginalModule')

        source_app = self._make_app('Source App', 'UpdatedModule')
        source = source_app.export_json(dump_json=False)

        overwrite_app_from_source(self.domain, target._id, source, {'name': 'Renamed'})

        updated = Application.get(target._id)
        assert updated.name == 'Renamed'
