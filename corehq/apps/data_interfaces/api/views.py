import json
from functools import wraps

from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from corehq import privileges, toggles
from corehq.apps.accounting.decorators import requires_privilege_with_fallback
from corehq.apps.api.decorators import api_throttle
from corehq.apps.data_interfaces.bulk_form_actions import create_bulk_form_job
from corehq.apps.data_interfaces.models import BulkAsyncJob
from corehq.apps.data_interfaces.tasks import bulk_form_action_async
from corehq.apps.domain.decorators import api_key_auth_header_only
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import HqPermissions
from corehq.form_processor.models import XFormInstance
from corehq.util.view_utils import reverse

from .bulk_form_action import UserError, serialize_job, validate_payload

NOT_FOUND_MESSAGE = 'Not found'


def require_access_all_locations(view):
    """Reject users whose role restricts them to specific locations.

    ``LocationAccessMiddleware`` runs before the API key is authenticated, so
    it cannot do this for us.
    """
    @wraps(view)
    def wrapped(request, domain, *args, **kwargs):
        if not request.couch_user.has_permission(domain, 'access_all_locations'):
            return JsonResponse(
                {'error': "This API is not available to location-restricted users"},
                status=403,
            )
        return view(request, domain, *args, **kwargs)

    return wrapped


@csrf_exempt
@api_key_auth_header_only
@toggles.BULK_FORM_ACTIONS_API.required_decorator(plain_message=NOT_FOUND_MESSAGE)
@require_permission(HqPermissions.edit_data)
@require_permission(HqPermissions.access_api)
@requires_privilege_with_fallback(privileges.API_ACCESS)
@requires_privilege_with_fallback(privileges.DATA_CLEANUP)
@require_access_all_locations
@api_throttle
def bulk_form_action(request, domain):
    if request.method != 'POST':
        return JsonResponse({'error': "Request method not allowed"}, status=405)

    try:
        action, form_ids = validate_payload(_parse_body(request))
    except UserError as e:
        return JsonResponse({'error': e.message}, status=400)

    job = create_bulk_form_job(
        domain,
        action,
        request.couch_user.username,
        form_ids,
        api_key=getattr(request, 'api_key', None),
    )
    bulk_form_action_async.delay(job.id.hex, domain)

    data = serialize_job(job)
    data['status_url'] = reverse(
        'bulk_form_action_status', args=[domain, job.id.hex], absolute=True)
    return JsonResponse(data, status=202)


@csrf_exempt
@api_key_auth_header_only
@toggles.BULK_FORM_ACTIONS_API.required_decorator(plain_message=NOT_FOUND_MESSAGE)
@require_permission(HqPermissions.edit_data)
@require_permission(HqPermissions.access_api)
@requires_privilege_with_fallback(privileges.API_ACCESS)
@requires_privilege_with_fallback(privileges.DATA_CLEANUP)
@require_access_all_locations
@api_throttle
def bulk_form_action_status(request, domain, job_id):
    if request.method != 'GET':
        return JsonResponse({'error': "Request method not allowed"}, status=405)

    try:
        job = BulkAsyncJob.objects.get(
            id=job_id, domain=domain, model=XFormInstance)
    except (BulkAsyncJob.DoesNotExist, ValueError, ValidationError):
        return JsonResponse({'error': f"Job '{job_id}' not found"}, status=404)

    return JsonResponse(serialize_job(job))


def _parse_body(request):
    try:
        return json.loads(request.body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise UserError("Payload must be valid JSON")
