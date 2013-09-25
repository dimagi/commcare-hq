from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import HttpResponse
from corehq.apps.telerivet.tasks import process_incoming_message

@require_POST
@csrf_exempt
def incoming_message(request):
    process_incoming_message.delay(request)
    return HttpResponse()

