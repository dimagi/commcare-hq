from __future__ import absolute_import
from __future__ import unicode_literals
from django.http import HttpResponse
from corehq.apps.sms.api import incoming as incoming_sms
from corehq.messaging.smsbackends.sislog.util import convert_raw_string


def sms_in(request):
    """
    sender - the number of the person sending the sms
    receiver - the number the sms was sent to
    msgdata - the message
    """
    sender = request.GET.get("sender", None)
    receiver = request.GET.get("receiver", None)
    msgdata = request.GET.get("msgdata", None)
    if sender is None or msgdata is None:
        return HttpResponse(status=400)
    else:
        cleaned_text = convert_raw_string(msgdata)
        incoming_sms(sender, cleaned_text, "SISLOG", raw_text=msgdata)
        return HttpResponse()

