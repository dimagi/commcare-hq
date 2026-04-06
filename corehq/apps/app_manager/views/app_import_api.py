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


def _handle_import_app(request, domain):
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


@json_error
@require_permission(HqPermissions.edit_apps, login_decorator=api_auth())
@api_throttle
@require_POST
def import_app_api(request, domain):
    return _handle_import_app(request, domain)


def _handle_upload_multimedia(request, domain, app_id):
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
        with zipfile.ZipFile(uploaded_file) as zf:
            if zf.testzip() is not None:
                return JsonResponse(
                    {'success': False, 'error': 'ZIP file is corrupt'}, status=400
                )
    except zipfile.BadZipFile:
        return JsonResponse(
            {'success': False, 'error': 'Uploaded file is not a valid ZIP file'}, status=400
        )

    uploaded_file.seek(0)
    processing_id, _ = save_multimedia_upload(uploaded_file)

    username = request.couch_user.username if request.couch_user else None
    process_bulk_upload_zip.delay(
        processing_id, domain, app_id, username=username
    )

    return JsonResponse({'success': True, 'processing_id': processing_id})


@json_error
@require_permission(HqPermissions.edit_apps, login_decorator=api_auth())
@api_throttle
@require_POST
def upload_multimedia_api(request, domain, app_id):
    return _handle_upload_multimedia(request, domain, app_id)


def _handle_multimedia_status(request, domain, app_id, processing_id):
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


@json_error
@require_permission(HqPermissions.edit_apps, login_decorator=api_auth())
@api_throttle
@require_GET
def multimedia_status_api(request, domain, app_id, processing_id):
    return _handle_multimedia_status(request, domain, app_id, processing_id)
