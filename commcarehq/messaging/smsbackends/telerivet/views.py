from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import HttpResponse
from commcarehq.messaging.smsbackends.telerivet.tasks import process_incoming_message

# Tuple of (hq field name, telerivet field name) tuples
TELERIVET_INBOUND_FIELD_MAP = (
    ('event', 'event'),
    ('message_id', 'id'),
    ('message_type', 'message_type'),
    ('content', 'content'),
    ('from_number', 'from_number'),
    ('from_number_e164', 'from_number_e164'),
    ('to_number', 'to_number'),
    ('time_created', 'time_created'),
    ('time_sent', 'time_sent'),
    ('contact_id', 'contact_id'),
    ('phone_id', 'phone_id'),
    ('service_id', 'service_id'),
    ('project_id', 'project_id'),
    ('secret', 'secret'),
)

@require_POST
@csrf_exempt
def incoming_message(request):
    kwargs = {a: request.POST.get(b) for (a, b) in TELERIVET_INBOUND_FIELD_MAP}
    process_incoming_message.delay(**kwargs)
    return HttpResponse()
