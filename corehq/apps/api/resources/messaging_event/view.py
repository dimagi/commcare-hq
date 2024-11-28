from django.http import HttpResponseNotFound, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from tastypie.exceptions import BadRequest

from corehq import privileges
from corehq.apps.accounting.decorators import requires_privilege_with_fallback
from corehq.apps.api.decorators import allow_cors, api_throttle
from corehq.apps.api.resources.messaging_event.filters import filter_query
from corehq.apps.api.resources.messaging_event.pagination import get_paged_data
from corehq.apps.api.resources.messaging_event.serializers import (
    serialize_event,
)
from corehq.apps.api.resources.messaging_event.utils import (
    get_request_params,
    sort_query,
)
from corehq.apps.case_importer.views import require_can_edit_data
from corehq.apps.domain.decorators import api_auth
from corehq.apps.sms.models import MessagingSubEvent


@csrf_exempt
@allow_cors(['OPTIONS', 'GET'])
@api_auth()
@require_can_edit_data
@requires_privilege_with_fallback(privileges.API_ACCESS)
@api_throttle
def messaging_events(request, domain, api_version, event_id=None):
    """Despite it's name this API is backed by the MessagingSubEvent model
    which has a more direct relationship with who the messages are being sent to.
    Each event may have more than one actual message associated with it.
    """
    try:
        if request.method == 'GET' and event_id:
            return _get_individual(request, event_id)
        if request.method == 'GET' and not event_id:
            return _get_list(request, api_version)
        return JsonResponse({'error': "Request method not allowed"}, status=405)
    except BadRequest as e:
        return JsonResponse({'error': str(e)}, status=400)


def _get_individual(request, event_id):
    try:
        event = _get_base_query(request.domain).get(id=event_id)
    except MessagingSubEvent.DoesNotExist:
        return HttpResponseNotFound()

    return JsonResponse(serialize_event(event))


def _get_list(request, api_version):
    request_params = get_request_params(request)
    query = _get_base_query(request.domain)
    filtered_query = filter_query(query, request_params)
    sorted_query = sort_query(filtered_query, request_params)
    data = get_paged_data(sorted_query, request_params, api_version)
    return JsonResponse(data)


def _get_base_query(domain):
    return MessagingSubEvent.objects.select_related("parent").filter(domain=domain)
