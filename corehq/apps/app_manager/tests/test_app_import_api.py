import json
import zipfile
from io import BytesIO
from unittest.mock import MagicMock, patch

from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, SimpleTestCase

from couchdbkit.exceptions import ResourceNotFound
from soil.exceptions import TaskFailedError

from corehq.apps.app_manager.views.app_import_api import (
    _handle_import_app as import_app_api,
    _handle_multimedia_status as multimedia_status_api,
    _handle_upload_multimedia as upload_multimedia_api,
)


class TestImportAppAPI(SimpleTestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.domain = 'test-domain'

    def _make_request(self, app_name=None, app_file_content=None):
        data = {}
        if app_name:
            data['app_name'] = app_name
        if app_file_content is not None:
            f = BytesIO(app_file_content)
            f.name = 'app.json'
            data['app_file'] = f

        request = self.factory.post('/fake-url/', data=data)
        request.couch_user = MagicMock()
        request.couch_user.username = 'testuser'
        setattr(request, 'session', 'session')
        messages = FallbackStorage(request)
        setattr(request, '_messages', messages)
        return request

    def test_missing_app_name(self):
        request = self._make_request(
            app_file_content=json.dumps({'doc_type': 'Application'}).encode()
        )
        response = import_app_api(request, self.domain)
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn('app_name', data['error'])

    def test_missing_app_file(self):
        request = self._make_request(app_name='My App')
        response = import_app_api(request, self.domain)
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn('app_file', data['error'])

    def test_invalid_json_file(self):
        request = self._make_request(
            app_name='My App',
            app_file_content=b'not json at all',
        )
        response = import_app_api(request, self.domain)
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn('JSON', data['error'])

    @patch('corehq.apps.app_manager.views.app_import_api.import_app_util')
    def test_successful_import(self, mock_import):
        mock_app = MagicMock()
        mock_app._id = 'abc123'
        mock_import.return_value = mock_app

        request = self._make_request(
            app_name='My App',
            app_file_content=json.dumps({'doc_type': 'Application'}).encode(),
        )
        response = import_app_api(request, self.domain)
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['app_id'], 'abc123')

        mock_import.assert_called_once()
        call_args = mock_import.call_args
        self.assertEqual(call_args[0][1], self.domain)
        self.assertEqual(call_args[0][2], {'name': 'My App'})

    @patch('corehq.apps.app_manager.views.app_import_api.import_app_util')
    def test_successful_import_with_warnings(self, mock_import):
        mock_app = MagicMock()
        mock_app._id = 'abc123'

        def import_with_warning(source, domain, extra, request=None):
            from django.contrib import messages
            messages.warning(request, "Missing multimedia file(s).")
            return mock_app

        mock_import.side_effect = import_with_warning

        request = self._make_request(
            app_name='My App',
            app_file_content=json.dumps({'doc_type': 'Application'}).encode(),
        )
        response = import_app_api(request, self.domain)
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['app_id'], 'abc123')
        self.assertIn('warnings', data)
        self.assertEqual(len(data['warnings']), 1)
        self.assertIn('Missing multimedia', data['warnings'][0])


class TestUploadMultimediaAPI(SimpleTestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.domain = 'test-domain'

    def _make_zip_file(self):
        buf = BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            zf.writestr('images/icon.png', b'\x89PNG fake data')
        buf.seek(0)
        buf.name = 'multimedia.zip'
        return buf

    def _make_request(self, upload_file=None):
        data = {}
        if upload_file is not None:
            data['bulk_upload_file'] = upload_file
        request = self.factory.post('/fake-url/', data=data)
        request.couch_user = MagicMock()
        request.couch_user.username = 'testuser'
        return request

    def test_missing_file(self):
        request = self._make_request()
        with patch('corehq.apps.app_manager.views.app_import_api.get_app'):
            response = upload_multimedia_api(request, self.domain, 'app123')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn('bulk_upload_file', data['error'])

    def test_invalid_zip(self):
        bad_file = BytesIO(b'not a zip')
        bad_file.name = 'bad.zip'
        request = self._make_request(upload_file=bad_file)
        with patch('corehq.apps.app_manager.views.app_import_api.get_app'):
            response = upload_multimedia_api(request, self.domain, 'app123')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn('ZIP', data['error'])

    @patch('corehq.apps.app_manager.views.app_import_api.save_multimedia_upload')
    @patch('corehq.apps.app_manager.views.app_import_api.process_bulk_upload_zip')
    @patch('corehq.apps.app_manager.views.app_import_api.get_app')
    def test_successful_upload(self, mock_get_app, mock_task, mock_save):
        mock_get_app.return_value = MagicMock()
        mock_task.delay = MagicMock()
        mock_save.return_value = ('proc-abc123', MagicMock())

        zip_file = self._make_zip_file()
        request = self._make_request(upload_file=zip_file)
        response = upload_multimedia_api(request, self.domain, 'app123')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['processing_id'], 'proc-abc123')
        mock_save.assert_called_once()
        mock_task.delay.assert_called_once()

    @patch('corehq.apps.app_manager.views.app_import_api.get_app')
    def test_app_not_found(self, mock_get_app):
        mock_get_app.side_effect = ResourceNotFound()

        zip_file = self._make_zip_file()
        request = self._make_request(upload_file=zip_file)
        response = upload_multimedia_api(request, self.domain, 'app123')
        self.assertEqual(response.status_code, 404)


class TestMultimediaStatusAPI(SimpleTestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.domain = 'test-domain'

    def _make_request(self):
        request = self.factory.get('/fake-url/')
        request.couch_user = MagicMock()
        return request

    @patch('corehq.apps.app_manager.views.app_import_api.get_app')
    @patch('corehq.apps.app_manager.views.app_import_api.get_download_context')
    @patch('corehq.apps.app_manager.views.app_import_api.BulkMultimediaStatusCache')
    def test_successful_status(self, mock_cache_cls, mock_download_ctx, mock_get_app):
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

        request = self._make_request()
        response = multimedia_status_api(request, self.domain, 'app123', 'proc123')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertFalse(data['complete'])
        self.assertEqual(data['progress']['current'], 5)

    @patch('corehq.apps.app_manager.views.app_import_api.get_app')
    @patch('corehq.apps.app_manager.views.app_import_api.get_download_context')
    @patch('corehq.apps.app_manager.views.app_import_api.BulkMultimediaStatusCache')
    def test_expired_processing_id(self, mock_cache_cls, mock_download_ctx, mock_get_app):
        mock_get_app.return_value = MagicMock()
        mock_download_ctx.return_value = {}
        mock_cache_cls.get.return_value = None

        request = self._make_request()
        response = multimedia_status_api(request, self.domain, 'app123', 'proc123')
        self.assertEqual(response.status_code, 404)

    @patch('corehq.apps.app_manager.views.app_import_api.get_app')
    @patch('corehq.apps.app_manager.views.app_import_api.get_download_context')
    def test_task_failed(self, mock_download_ctx, mock_get_app):
        mock_get_app.return_value = MagicMock()
        mock_download_ctx.side_effect = TaskFailedError()

        request = self._make_request()
        response = multimedia_status_api(request, self.domain, 'app123', 'proc123')
        self.assertEqual(response.status_code, 500)
        data = json.loads(response.content)
        self.assertIn('error', data)

    @patch('corehq.apps.app_manager.views.app_import_api.get_app')
    def test_app_not_found(self, mock_get_app):
        mock_get_app.side_effect = ResourceNotFound()

        request = self._make_request()
        response = multimedia_status_api(request, self.domain, 'app123', 'proc123')
        self.assertEqual(response.status_code, 404)
