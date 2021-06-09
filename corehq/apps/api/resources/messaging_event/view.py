from urllib.parse import urlencode

from django.http import JsonResponse, HttpResponseNotFound
from django.views.decorators.csrf import csrf_exempt
from tastypie.exceptions import BadRequest

from corehq import privileges
from corehq.apps.accounting.decorators import requires_privilege_with_fallback
from corehq.apps.api.decorators import allow_cors
from corehq.apps.api.resources.messaging_event.filters import filter_query
from corehq.apps.api.resources.messaging_event.serializers import serialize_event
from corehq.apps.api.resources.messaging_event.utils import sort_query, get_limit_offset
from corehq.apps.case_importer.views import require_can_edit_data
from corehq.apps.domain.decorators import api_auth
from corehq.apps.sms.models import MessagingSubEvent


@csrf_exempt
@allow_cors(['OPTIONS', 'GET'])
@api_auth
@require_can_edit_data
@requires_privilege_with_fallback(privileges.API_ACCESS)
def messaging_events(request, domain, event_id=None):
    """Despite it's name this API is backed by the MessagingSubEvent model
    which has a more direct relationship with who the messages are being sent to.
    Each event may have more than one actual message associated with it.
    """
    try:
        if request.method == 'GET' and event_id:
            return _get_individual(request, event_id)
        if request.method == 'GET' and not event_id:
            return _get_list(request)
        return JsonResponse({'error': "Request method not allowed"}, status=405)
    except BadRequest as e:
        return JsonResponse({'error': str(e)}, status=400)


def _get_individual(request, event_id):
    try:
        event = MessagingSubEvent.objects.select_related("parent").get(
            parent__domain=request.domain, id=event_id
        )
    except MessagingSubEvent.DoesNotExist:
        return HttpResponseNotFound()

    return JsonResponse(serialize_event(event))


def _get_list(request):
    request_data = request.GET.dict()
    query = MessagingSubEvent.objects.select_related("parent").filter(parent__domain=request.domain)
    filtered_query = filter_query(query, request_data)
    sorted_query = sort_query(filtered_query, request_data)
    data = _get_response_data(sorted_query, request_data)
    return JsonResponse(data)


def _get_response_data(query, request_data):
    limit = get_limit_offset("limit", request_data, 20, max_value=1000)
    offset = get_limit_offset("offset", request_data, 0)
    if limit == 0:
        objects = list(query[offset:])
    else:
        objects = list(query[offset:offset + limit])
    if objects:
        next_vals = {"offset": str(offset + limit), "limit": str(limit)}
        request_data.update(next_vals)
        meta_next = urlencode(request_data)
    else:
        meta_next = None
    return {
        "objects": [serialize_event(event) for event in objects],
        "meta": {
            "limit": limit,
            "offset": offset,
            "next": f"?{meta_next}" if meta_next else None
        }
    }
