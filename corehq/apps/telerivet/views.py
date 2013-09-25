from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import HttpResponse
from corehq.apps.telerivet.tasks import process_incoming_message

@require_POST
@csrf_exempt
def incoming_message(request):
    kwargs = {
        "event" : request.POST.get("event"),
        "message_id" : request.POST.get("id"),
        "message_type" : request.POST.get("message_type"),
        "from_number" : request.POST.get("from_number"),
        "contact_id" : request.POST.get("contact_id"),
        "phone_id" : request.POST.get("phone_id"),
        "to_number" : request.POST.get("to_number"),
        "time_created" : request.POST.get("time_created"),
        "time_sent" : request.POST.get("time_sent"),
        "content" : request.POST.get("content"),
        "project_id" : request.POST.get("project_id"),
        "secret" : request.POST.get("secret"),
    }

    process_incoming_message.delay(**kwargs)
    return HttpResponse()

