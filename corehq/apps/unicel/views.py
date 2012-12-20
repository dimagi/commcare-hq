from django.http import HttpResponse
from corehq.apps.sms.util import domains_for_phone, users_for_phone
from corehq.apps.unicel import api
import json

def incoming(request):
    """
    The inbound endpoint for UNICEL's API.
    """
    # for now just save this information in the message log and return
    message = api.create_from_request(request)
    return HttpResponse(json.dumps({'status': 'success', 'message_id': message._id}), 'text/json')
