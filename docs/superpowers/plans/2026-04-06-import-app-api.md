# Import App API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add three API endpoints for programmatic app import and multimedia upload, sitting alongside existing app manager API views.

**Architecture:** Function-based views in a new module following the `cli.py` pattern. The import endpoint accepts JSON + app name, the multimedia endpoint accepts a ZIP and kicks off an async Celery task, and the status endpoint polls that task's progress. All reuse existing core logic (`import_app()`, `process_bulk_upload_zip`). The file-storage-and-cache-setup logic currently in `ProcessBulkUploadView.process_upload()` is extracted into a shared utility so both the existing view and the new API can call it.

**Tech Stack:** Django views, `@api_auth()` + `@require_permission` decorators, `JsonResponse`, existing Celery tasks, `BulkMultimediaStatusCache`

**Spec:** `docs/superpowers/specs/2026-04-06-import-app-api-design.md`

---

## File Structure

- **Create:** `corehq/apps/hqmedia/utils.py` — Shared `save_multimedia_upload` utility extracted from `ProcessBulkUploadView.process_upload()`
- **Modify:** `corehq/apps/hqmedia/views.py` — Update `ProcessBulkUploadView.process_upload()` to call the shared utility
- **Create:** `corehq/apps/app_manager/views/app_import_api.py` — Three API view functions
- **Modify:** `corehq/apps/app_manager/urls.py` — Add URL patterns for the three endpoints
- **Create:** `corehq/apps/app_manager/tests/test_app_import_api.py` — Tests for the API endpoints
- **Create:** `corehq/apps/hqmedia/tests/test_utils.py` — Tests for the shared utility

---

### Task 1: Extract shared multimedia upload utility — Tests

**Files:**
- Create: `corehq/apps/hqmedia/tests/test_utils.py`

- [ ] **Step 1: Write failing tests for save_multimedia_upload**

```python
import zipfile
from io import BytesIO
from unittest.mock import patch, MagicMock

from django.test import TestCase, SimpleTestCase

from corehq.apps.hqmedia.utils import save_multimedia_upload


class TestSaveMultimediaUpload(SimpleTestCase):

    def _make_zip_file(self):
        buf = BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            zf.writestr('images/icon.png', b'\x89PNG fake data')
        buf.seek(0)
        buf.name = 'multimedia.zip'
        return buf

    @patch('corehq.apps.hqmedia.utils.expose_cached_download')
    def test_returns_processing_id(self, mock_expose):
        mock_saved = MagicMock()
        mock_saved.download_id = 'dl-abc123'
        mock_expose.return_value = mock_saved

        uploaded_file = self._make_zip_file()
        processing_id = save_multimedia_upload(uploaded_file)
        self.assertEqual(processing_id, 'dl-abc123')
        mock_expose.assert_called_once()

    @patch('corehq.apps.hqmedia.utils.expose_cached_download')
    def test_reads_file_content(self, mock_expose):
        mock_saved = MagicMock()
        mock_saved.download_id = 'dl-abc123'
        mock_expose.return_value = mock_saved

        uploaded_file = self._make_zip_file()
        save_multimedia_upload(uploaded_file)

        call_args = mock_expose.call_args
        # First positional arg is the file content (bytes)
        self.assertIsInstance(call_args[0][0], bytes)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && pytest corehq/apps/hqmedia/tests/test_utils.py -v --no-header 2>&1 | head -20`
Expected: ImportError — `save_multimedia_upload` does not exist yet

- [ ] **Step 3: Commit test file**

```bash
git add corehq/apps/hqmedia/tests/test_utils.py
git commit -m "test: add tests for save_multimedia_upload utility"
```

---

### Task 2: Extract shared multimedia upload utility — Implementation

**Files:**
- Create: `corehq/apps/hqmedia/utils.py`

- [ ] **Step 1: Create the shared utility**

```python
import shutil
import uuid

from django.conf import settings

from soil import DownloadBase
from soil.util import expose_cached_download

from corehq.apps.hqmedia.cache import (
    BulkMultimediaStatusCache,
    BulkMultimediaStatusCacheNfs,
)
from corehq.util.files import file_extention_from_filename


def save_multimedia_upload(uploaded_file):
    """Save an uploaded multimedia ZIP file and return a processing_id.

    Handles both NFS-backed (temporary_file_path) and in-memory uploads.
    Creates a BulkMultimediaStatusCache entry for tracking.

    Returns the processing_id to pass to process_bulk_upload_zip.
    """
    if hasattr(uploaded_file, 'temporary_file_path') and settings.SHARED_DRIVE_CONF.temp_dir:
        prefix = DownloadBase.new_id_prefix
        processing_id = prefix + uuid.uuid4().hex
        path = settings.SHARED_DRIVE_CONF.get_temp_file(suffix='.upload')
        shutil.move(uploaded_file.temporary_file_path(), path)
        status = BulkMultimediaStatusCacheNfs(processing_id, path)
        status.save()
    else:
        uploaded_file.file.seek(0)
        saved_file = expose_cached_download(
            uploaded_file.file.read(),
            expiry=BulkMultimediaStatusCache.cache_expiry,
            file_extension=file_extention_from_filename(uploaded_file.name),
        )
        processing_id = saved_file.download_id
        status = BulkMultimediaStatusCache(processing_id)
        status.save()

    return processing_id
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `source .venv/bin/activate && pytest corehq/apps/hqmedia/tests/test_utils.py -v --no-header 2>&1 | head -20`
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add corehq/apps/hqmedia/utils.py
git commit -m "refactor: extract save_multimedia_upload utility from ProcessBulkUploadView"
```

---

### Task 3: Update ProcessBulkUploadView to use shared utility

**Files:**
- Modify: `corehq/apps/hqmedia/views.py:631-657`

- [ ] **Step 1: Replace the file-storage logic in process_upload**

Replace the `process_upload` method of `ProcessBulkUploadView` (lines 631-657) with:

```python
    def process_upload(self):
        from corehq.apps.hqmedia.utils import save_multimedia_upload

        processing_id = save_multimedia_upload(self.uploaded_file)

        process_bulk_upload_zip.delay(processing_id, self.domain, self.app_id,
                                      username=self.username,
                                      share_media=self.share_media,
                                      license_name=self.license_used,
                                      author=self.author,
                                      attribution_notes=self.attribution_notes)

        status = BulkMultimediaStatusCache.get(processing_id)
        return status.get_response()
```

- [ ] **Step 2: Remove now-unused imports from views.py if any**

Check if `shutil`, `uuid`, `DownloadBase`, `expose_cached_download`,
`BulkMultimediaStatusCacheNfs`, or `file_extention_from_filename` are
still used elsewhere in `views.py`. Remove only if unused.

- [ ] **Step 3: Run existing hqmedia tests to verify nothing broke**

Run: `source .venv/bin/activate && pytest corehq/apps/hqmedia/tests/ -v --no-header 2>&1 | tail -20`
Expected: All existing tests pass

- [ ] **Step 4: Commit**

```bash
git add corehq/apps/hqmedia/views.py
git commit -m "refactor: use save_multimedia_upload in ProcessBulkUploadView"
```

---

### Task 4: Import App API View — Tests

**Files:**
- Create: `corehq/apps/app_manager/tests/test_app_import_api.py`

- [ ] **Step 1: Write failing tests for import_app_api**

```python
import json
import zipfile
from io import BytesIO
from unittest.mock import patch, MagicMock

from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import TestCase, RequestFactory

from couchdbkit.exceptions import ResourceNotFound
from soil.exceptions import TaskFailedError

from corehq.apps.app_manager.views.app_import_api import import_app_api


class TestImportAppAPI(TestCase):

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
        # Set up Django messages framework for request
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && pytest corehq/apps/app_manager/tests/test_app_import_api.py -v --no-header 2>&1 | head -30`
Expected: ImportError — `import_app_api` does not exist yet

- [ ] **Step 3: Commit test file**

```bash
git add corehq/apps/app_manager/tests/test_app_import_api.py
git commit -m "test: add tests for import_app_api endpoint"
```

---

### Task 5: Import App API View — Implementation

**Files:**
- Create: `corehq/apps/app_manager/views/app_import_api.py`

- [ ] **Step 1: Implement import_app_api**

```python
import json
import zipfile

from django.contrib.messages import get_messages
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from couchdbkit.exceptions import ResourceNotFound

from soil.exceptions import TaskFailedError
from soil.util import get_download_context

from corehq.apps.api.decorators import api_throttle
from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.models import import_app as import_app_util
from corehq.apps.domain.decorators import api_auth
from corehq.apps.hqmedia.cache import BulkMultimediaStatusCache
from corehq.apps.hqmedia.tasks import process_bulk_upload_zip
from corehq.apps.hqmedia.utils import save_multimedia_upload
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import HqPermissions
from corehq.util.view_utils import json_error


@json_error
@require_permission(HqPermissions.edit_apps, login_decorator=api_auth())
@api_throttle
@require_POST
def import_app_api(request, domain):
    app_name = request.POST.get('app_name')
    if not app_name:
        return JsonResponse({'success': False, 'error': 'app_name is required'}, status=400)

    app_file = request.FILES.get('app_file')
    if not app_file:
        return JsonResponse({'success': False, 'error': 'app_file is required'}, status=400)

    try:
        source = json.load(app_file)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'success': False, 'error': 'Invalid JSON file'}, status=400)

    if not source:
        return JsonResponse({'success': False, 'error': 'Invalid JSON file'}, status=400)

    app = import_app_util(source, domain, {'name': app_name}, request=request)

    response = {'success': True, 'app_id': app._id}
    warnings = [str(m) for m in get_messages(request)]
    if warnings:
        response['warnings'] = warnings
    return JsonResponse(response, status=201)
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `source .venv/bin/activate && pytest corehq/apps/app_manager/tests/test_app_import_api.py -v --no-header 2>&1 | head -30`
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add corehq/apps/app_manager/views/app_import_api.py
git commit -m "feat: add import_app_api endpoint"
```

---

### Task 6: Upload Multimedia API — Tests

**Files:**
- Modify: `corehq/apps/app_manager/tests/test_app_import_api.py`

- [ ] **Step 1: Write failing tests for upload_multimedia_api**

Add to `test_app_import_api.py` (imports already at module level):

```python
from corehq.apps.app_manager.views.app_import_api import upload_multimedia_api


class TestUploadMultimediaAPI(TestCase):

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
        mock_save.return_value = 'proc-abc123'

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && pytest corehq/apps/app_manager/tests/test_app_import_api.py::TestUploadMultimediaAPI -v --no-header 2>&1 | head -30`
Expected: ImportError — `upload_multimedia_api` does not exist yet

- [ ] **Step 3: Commit**

```bash
git add corehq/apps/app_manager/tests/test_app_import_api.py
git commit -m "test: add tests for upload_multimedia_api endpoint"
```

---

### Task 7: Upload Multimedia API — Implementation

**Files:**
- Modify: `corehq/apps/app_manager/views/app_import_api.py`

- [ ] **Step 1: Add upload_multimedia_api to app_import_api.py**

All imports are already present from Task 5. Add the view function:

```python
@json_error
@require_permission(HqPermissions.edit_apps, login_decorator=api_auth())
@api_throttle
@require_POST
def upload_multimedia_api(request, domain, app_id):
    try:
        get_app(domain, app_id)
    except ResourceNotFound:
        return JsonResponse(
            {'success': False, 'error': 'Application not found'}, status=404
        )

    uploaded_file = request.FILES.get('bulk_upload_file')
    if not uploaded_file:
        return JsonResponse(
            {'success': False, 'error': 'bulk_upload_file is required'}, status=400
        )

    try:
        zf = zipfile.ZipFile(uploaded_file)
    except Exception:
        return JsonResponse(
            {'success': False, 'error': 'Uploaded file is not a valid ZIP file'}, status=400
        )

    if zf.testzip() is not None:
        return JsonResponse(
            {'success': False, 'error': 'ZIP file is corrupt'}, status=400
        )

    uploaded_file.seek(0)
    processing_id = save_multimedia_upload(uploaded_file)

    username = request.couch_user.username if request.couch_user else None
    process_bulk_upload_zip.delay(
        processing_id, domain, app_id, username=username
    )

    return JsonResponse({'success': True, 'processing_id': processing_id})
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `source .venv/bin/activate && pytest corehq/apps/app_manager/tests/test_app_import_api.py -v --no-header 2>&1 | head -30`
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add corehq/apps/app_manager/views/app_import_api.py
git commit -m "feat: add upload_multimedia_api endpoint"
```

---

### Task 8: Multimedia Status API — Tests

**Files:**
- Modify: `corehq/apps/app_manager/tests/test_app_import_api.py`

- [ ] **Step 1: Write failing tests for multimedia_status_api**

Add to `test_app_import_api.py` (imports already at module level):

```python
from corehq.apps.app_manager.views.app_import_api import multimedia_status_api


class TestMultimediaStatusAPI(TestCase):

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && pytest corehq/apps/app_manager/tests/test_app_import_api.py::TestMultimediaStatusAPI -v --no-header 2>&1 | head -30`
Expected: ImportError — `multimedia_status_api` does not exist yet

- [ ] **Step 3: Commit**

```bash
git add corehq/apps/app_manager/tests/test_app_import_api.py
git commit -m "test: add tests for multimedia_status_api endpoint"
```

---

### Task 9: Multimedia Status API — Implementation

**Files:**
- Modify: `corehq/apps/app_manager/views/app_import_api.py`

- [ ] **Step 1: Add multimedia_status_api to app_import_api.py**

```python
@json_error
@require_permission(HqPermissions.edit_apps, login_decorator=api_auth())
@api_throttle
@require_GET
def multimedia_status_api(request, domain, app_id, processing_id):
    try:
        get_app(domain, app_id)
    except ResourceNotFound:
        return JsonResponse(
            {'success': False, 'error': 'Application not found'}, status=404
        )

    try:
        get_download_context(processing_id)
    except TaskFailedError:
        return JsonResponse(
            {'success': False, 'error': 'Multimedia processing task failed'},
            status=500
        )

    status = BulkMultimediaStatusCache.get(processing_id)
    if status is None:
        return JsonResponse(
            {'success': False, 'error': 'Processing ID not found or expired'},
            status=404
        )

    response_data = status.get_response()
    response_data['success'] = True
    return JsonResponse(response_data)
```

- [ ] **Step 2: Run all tests to verify they pass**

Run: `source .venv/bin/activate && pytest corehq/apps/app_manager/tests/test_app_import_api.py -v --no-header 2>&1 | head -40`
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add corehq/apps/app_manager/views/app_import_api.py
git commit -m "feat: add multimedia_status_api endpoint"
```

---

### Task 10: URL Registration

**Files:**
- Modify: `corehq/apps/app_manager/urls.py:88-99` (imports section)
- Modify: `corehq/apps/app_manager/urls.py:256-257` (api URL section)

- [ ] **Step 1: Add imports to urls.py**

Add after the existing `cli` imports around line 88:

```python
from corehq.apps.app_manager.views.app_import_api import (
    import_app_api,
    multimedia_status_api,
    upload_multimedia_api,
)
```

- [ ] **Step 2: Add URL patterns**

Add after line 257 (after `url(r'^api/download_ccz/$', direct_ccz, name='direct_ccz'),`):

```python
url(r'^api/import_app/$', import_app_api, name='import_app_api'),
url(r'^api/(?P<app_id>[\w-]+)/multimedia/$', upload_multimedia_api, name='upload_multimedia_api'),
url(r'^api/(?P<app_id>[\w-]+)/multimedia/status/(?P<processing_id>[\w-]+)/$',
    multimedia_status_api, name='multimedia_status_api'),
```

- [ ] **Step 3: Run all tests to verify nothing is broken**

Run: `source .venv/bin/activate && pytest corehq/apps/app_manager/tests/test_app_import_api.py corehq/apps/hqmedia/tests/test_utils.py -v --no-header 2>&1 | head -40`
Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add corehq/apps/app_manager/urls.py
git commit -m "feat: register import app API URL patterns"
```

---

### Task 11: Lint and Final Verification

- [ ] **Step 1: Run ruff on all new/modified files**

Run: `source .venv/bin/activate && ruff check corehq/apps/app_manager/views/app_import_api.py corehq/apps/app_manager/tests/test_app_import_api.py corehq/apps/app_manager/urls.py corehq/apps/hqmedia/utils.py corehq/apps/hqmedia/tests/test_utils.py corehq/apps/hqmedia/views.py`

- [ ] **Step 2: Fix any lint issues**

Run: `source .venv/bin/activate && ruff check --fix corehq/apps/app_manager/views/app_import_api.py corehq/apps/app_manager/tests/test_app_import_api.py corehq/apps/hqmedia/utils.py corehq/apps/hqmedia/tests/test_utils.py corehq/apps/hqmedia/views.py && ruff format corehq/apps/app_manager/views/app_import_api.py corehq/apps/app_manager/tests/test_app_import_api.py corehq/apps/hqmedia/utils.py corehq/apps/hqmedia/tests/test_utils.py`

- [ ] **Step 3: Run full test suite one final time**

Run: `source .venv/bin/activate && pytest corehq/apps/app_manager/tests/test_app_import_api.py corehq/apps/hqmedia/tests/test_utils.py -v --no-header`
Expected: All tests pass

- [ ] **Step 4: Commit any lint fixes**

```bash
git add corehq/apps/app_manager/views/app_import_api.py corehq/apps/app_manager/tests/test_app_import_api.py corehq/apps/hqmedia/utils.py corehq/apps/hqmedia/tests/test_utils.py corehq/apps/hqmedia/views.py
git commit -m "style: lint fixes for import app API"
```
