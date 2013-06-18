from django.http import HttpResponse
from corehq.apps.sms.api import incoming as incoming_sms

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
        incoming_sms(sender, msgdata, "SISLOG")
        return HttpResponse()

