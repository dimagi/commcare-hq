# Import App API Design

## Overview

API endpoints for importing applications and their multimedia, providing
programmatic access to the existing import_app functionality. These sit
alongside the existing app manager API endpoints (`list_apps`,
`direct_ccz`) under `/a/{domain}/apps/api/`.

## Endpoints

### 1. Import App

`POST /a/{domain}/apps/api/import_app/`

Accepts a multipart form upload with the app source JSON and a name for the
new application.

**Request (multipart/form-data):**
- `app_file` (file, required) - The application source JSON file
- `app_name` (string, required) - Name for the imported application

**Response (201):**
```json
{
  "success": true,
  "app_id": "<new_app_id>"
}
```

**Errors:**
- 400: Missing `app_file` or `app_name`, invalid JSON file
- 403: Insufficient permissions
- 405: Non-POST request

**Notes:**
- The uploaded file is validated as parseable JSON before being passed to
  `import_app()`.
- `import_app()` may issue `messages.warning()` for
  `ReportConfigurationNotFoundError` or `ResourceNotFound` (e.g., missing
  multimedia or UCR references). These warnings are captured and included in
  the response under a `"warnings"` key so API callers are aware of
  non-fatal issues.

### 2. Upload Multimedia

`POST /a/{domain}/apps/api/{app_id}/multimedia/`

Accepts a ZIP file containing multimedia assets for a previously imported
application. Processing happens asynchronously via the existing
`process_bulk_upload_zip` Celery task.

**Request (multipart/form-data):**
- `bulk_upload_file` (file, required) - ZIP archive of multimedia files

**Response (200):**
```json
{
  "success": true,
  "processing_id": "<id>"
}
```

**Errors:**
- 400: Missing file, not a valid ZIP, corrupt ZIP
- 404: App not found or does not belong to domain
- 405: Non-POST request

**Notes:**
- The app is validated to exist and belong to the given domain using
  `get_app(domain, app_id)`.
- The `username` parameter for `process_bulk_upload_zip` is taken from
  `request.couch_user.username`.
- Other optional parameters (`share_media`, `license_name`, `author`,
  `attribution_notes`) default to empty/false, matching the browser form
  defaults.

### 3. Poll Multimedia Status

`GET /a/{domain}/apps/api/{app_id}/multimedia/status/{processing_id}/`

Returns the current processing status for an async multimedia upload.

**Response (200):**
```json
{
  "success": true,
  "complete": false,
  "in_celery": true,
  "progress": {
    "percent": 50,
    "current": 5,
    "total": 10
  },
  "errors": [],
  "matched_count": 3,
  "unmatched_count": 2,
  "total_files": 10,
  "processed_files": 5
}
```

When `complete` is `true`, the response includes full details:
`matched_files`, `unmatched_files`, `skipped_files`, `image_count`,
`audio_count`, `video_count`.

**Errors:**
- 404: App not found, or processing_id not found (cache expired or invalid)
- 500: Celery task failed (`TaskFailedError` from `get_download_context`)

**Notes:**
- Primary status comes from `BulkMultimediaStatusCache.get(processing_id)`.
- `get_download_context(processing_id)` is called first solely to detect
  `TaskFailedError`. The actual progress data comes from the cache.

## Authentication & Authorization

All endpoints use this decorator stack (matching `cli.py` pattern):
- `@json_error` - Wraps unhandled exceptions as JSON responses
- `@api_auth()` - Supports API key, basic auth, digest, OAuth
- `@api_throttle` - Standard API rate limiting
- `@require_can_edit_apps` - Requires `HqPermissions.edit_apps` permission

POST endpoints additionally use `@require_POST`.

## Implementation

### New file

`corehq/apps/app_manager/views/app_import_api.py`

Three function-based views following the `cli.py` pattern:

1. `import_app_api(request, domain)` - Validates the uploaded JSON file,
   calls `import_app()` from `corehq/apps/app_manager/models.py`, returns
   the new app ID. Captures Django messages from the request to include as
   warnings in the response.

2. `upload_multimedia_api(request, domain, app_id)` - Validates the app
   belongs to the domain via `get_app(domain, app_id)`. Validates the ZIP
   file. Saves it via `expose_cached_download` or shared drive (matching
   `ProcessBulkUploadView.process_upload`), launches
   `process_bulk_upload_zip` Celery task, returns the processing ID.
   Note: `process_bulk_upload_zip` uses `serializer='pickle'` - arguments
   must remain pickle-compatible (strings, not complex objects).

3. `multimedia_status_api(request, domain, app_id, processing_id)` -
   Calls `get_download_context()` to detect task failure, then gets the
   real status from `BulkMultimediaStatusCache.get(processing_id)`. Returns
   404 if the cache entry is None (expired or invalid ID).

### URL registration

In `corehq/apps/app_manager/urls.py`, alongside existing `api/` URLs:

```python
url(r'^api/import_app/$', import_app_api, name='import_app_api'),
url(r'^api/(?P<app_id>[\w-]+)/multimedia/$', upload_multimedia_api,
    name='upload_multimedia_api'),
url(r'^api/(?P<app_id>[\w-]+)/multimedia/status/(?P<processing_id>[\w-]+)/$',
    multimedia_status_api, name='multimedia_status_api'),
```

### Reused components

- `import_app()` from `corehq/apps/app_manager/models.py`
- `process_bulk_upload_zip` Celery task from `corehq/apps/hqmedia/tasks.py`
- `BulkMultimediaStatusCache` / `BulkMultimediaStatusCacheNfs` from
  `corehq/apps/hqmedia/cache.py`
- `expose_cached_download` from `soil.util`
- `get_download_context` from `soil.util`
- `get_app` from `corehq/apps/app_manager/dbaccessors.py`

### What is NOT included

- Source server metadata (source_server, source_domain, source_app_id)
- Multimedia instruction rendering (browser-specific)
- Any changes to existing views or forms
- File size limit enforcement (relies on Django's existing settings)
