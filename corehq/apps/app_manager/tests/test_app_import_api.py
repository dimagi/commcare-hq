import json
import zipfile
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory

from couchdbkit.exceptions import ResourceNotFound
from soil.exceptions import TaskFailedError

from corehq.apps.app_manager.views.app_import_api import (
    _handle_import_app,
    _handle_multimedia_status,
    _handle_upload_multimedia,
)

DOMAIN = 'test-domain'
MODULE = 'corehq.apps.app_manager.views.app_import_api'


def _make_import_request(app_name=None, app_file_content=None):
    data = {}
    if app_name:
        data['app_name'] = app_name
    if app_file_content is not None:
        f = BytesIO(app_file_content)
        f.name = 'app.json'
        data['app_file'] = f

    request = RequestFactory().post('/fake-url/', data=data)
    request.couch_user = MagicMock()
    request.couch_user.username = 'testuser'
    request.session = 'session'
    request._messages = FallbackStorage(request)
    return request


def _make_upload_request(upload_file=None):
    data = {}
    if upload_file is not None:
        data['bulk_upload_file'] = upload_file
    request = RequestFactory().post('/fake-url/', data=data)
    request.couch_user = MagicMock()
    request.couch_user.username = 'testuser'
    return request


def _make_zip_file():
    buf = BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        zf.writestr('images/icon.png', b'\x89PNG fake data')
    buf.seek(0)
    buf.name = 'multimedia.zip'
    return buf


def _json(response):
    return json.loads(response.content)


def _app_json():
    return json.dumps({'doc_type': 'Application'}).encode()


# --- import_app_api ---


@pytest.mark.parametrize('app_name, app_file_content, expected_error', [
    (None, _app_json(), 'app_name'),
    ('My App', None, 'app_file'),
    ('My App', b'not json at all', 'JSON'),
])
def test_import_app_validation_errors(app_name, app_file_content, expected_error):
    request = _make_import_request(app_name=app_name, app_file_content=app_file_content)
    response = _handle_import_app(request, DOMAIN)
    assert response.status_code == 400
    assert expected_error in _json(response)['error']


@patch(f'{MODULE}.import_app_util')
def test_import_app_success(mock_import):
    mock_app = MagicMock()
    mock_app._id = 'abc123'
    mock_import.return_value = mock_app

    request = _make_import_request(app_name='My App', app_file_content=_app_json())
    response = _handle_import_app(request, DOMAIN)

    assert response.status_code == 201
    data = _json(response)
    assert data['success'] is True
    assert data['app_id'] == 'abc123'
    mock_import.assert_called_once()
    assert mock_import.call_args[0][1] == DOMAIN
    assert mock_import.call_args[0][2] == {'name': 'My App'}


@patch(f'{MODULE}.import_app_util')
def test_import_app_captures_warnings(mock_import):
    mock_app = MagicMock()
    mock_app._id = 'abc123'

    def import_with_warning(source, domain, extra, request=None):
        from django.contrib import messages
        messages.warning(request, "Missing multimedia file(s).")
        return mock_app

    mock_import.side_effect = import_with_warning

    request = _make_import_request(app_name='My App', app_file_content=_app_json())
    response = _handle_import_app(request, DOMAIN)

    assert response.status_code == 201
    data = _json(response)
    assert data['success'] is True
    assert len(data['warnings']) == 1
    assert 'Missing multimedia' in data['warnings'][0]


# --- upload_multimedia_api ---


def test_upload_multimedia_missing_file():
    request = _make_upload_request()
    with patch(f'{MODULE}.get_app'):
        response = _handle_upload_multimedia(request, DOMAIN, 'app123')
    assert response.status_code == 400
    assert 'bulk_upload_file' in _json(response)['error']


def test_upload_multimedia_invalid_zip():
    bad_file = BytesIO(b'not a zip')
    bad_file.name = 'bad.zip'
    request = _make_upload_request(upload_file=bad_file)
    with patch(f'{MODULE}.get_app'):
        response = _handle_upload_multimedia(request, DOMAIN, 'app123')
    assert response.status_code == 400
    assert 'ZIP' in _json(response)['error']


@patch(f'{MODULE}.save_multimedia_upload')
@patch(f'{MODULE}.process_bulk_upload_zip')
@patch(f'{MODULE}.get_app')
def test_upload_multimedia_success(mock_get_app, mock_task, mock_save):
    mock_get_app.return_value = MagicMock()
    mock_task.delay = MagicMock()
    mock_save.return_value = ('proc-abc123', MagicMock())

    request = _make_upload_request(upload_file=_make_zip_file())
    response = _handle_upload_multimedia(request, DOMAIN, 'app123')

    assert response.status_code == 200
    data = _json(response)
    assert data['success'] is True
    assert data['processing_id'] == 'proc-abc123'
    mock_save.assert_called_once()
    mock_task.delay.assert_called_once()


@patch(f'{MODULE}.get_app', side_effect=ResourceNotFound())
def test_upload_multimedia_app_not_found(_mock_get_app):
    request = _make_upload_request(upload_file=_make_zip_file())
    response = _handle_upload_multimedia(request, DOMAIN, 'app123')
    assert response.status_code == 404


# --- multimedia_status_api ---


def _make_status_request():
    request = RequestFactory().get('/fake-url/')
    request.couch_user = MagicMock()
    return request


@patch(f'{MODULE}.get_app')
@patch(f'{MODULE}.get_download_context')
@patch(f'{MODULE}.BulkMultimediaStatusCache')
def test_multimedia_status_success(mock_cache_cls, mock_download_ctx, mock_get_app):
    mock_get_app.return_value = MagicMock()
    mock_download_ctx.return_value = {}
    mock_status = MagicMock()
    mock_status.get_response.return_value = {
        'complete': False,
        'in_celery': True,
        'progress': {'percent': 50, 'current': 5, 'total': 10},
        'errors': [],
        'processing_id': 'proc123',
    }
    mock_cache_cls.get.return_value = mock_status

    response = _handle_multimedia_status(_make_status_request(), DOMAIN, 'app123', 'proc123')

    assert response.status_code == 200
    data = _json(response)
    assert data['success'] is True
    assert data['complete'] is False
    assert data['progress']['current'] == 5


@patch(f'{MODULE}.get_app')
@patch(f'{MODULE}.get_download_context')
@patch(f'{MODULE}.BulkMultimediaStatusCache')
def test_multimedia_status_expired_processing_id(mock_cache_cls, mock_download_ctx, mock_get_app):
    mock_get_app.return_value = MagicMock()
    mock_download_ctx.return_value = {}
    mock_cache_cls.get.return_value = None

    response = _handle_multimedia_status(_make_status_request(), DOMAIN, 'app123', 'proc123')
    assert response.status_code == 404


@patch(f'{MODULE}.get_download_context', side_effect=TaskFailedError())
@patch(f'{MODULE}.get_app')
def test_multimedia_status_task_failed(mock_get_app, _mock_download_ctx):
    mock_get_app.return_value = MagicMock()

    response = _handle_multimedia_status(_make_status_request(), DOMAIN, 'app123', 'proc123')
    assert response.status_code == 500
    assert 'error' in _json(response)


@patch(f'{MODULE}.get_app', side_effect=ResourceNotFound())
def test_multimedia_status_app_not_found(_mock_get_app):
    response = _handle_multimedia_status(_make_status_request(), DOMAIN, 'app123', 'proc123')
    assert response.status_code == 404
