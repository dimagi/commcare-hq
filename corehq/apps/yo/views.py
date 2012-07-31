from django.http import HttpResponse
from corehq.apps.sms.api import incoming as incoming_sms

def sms_in(request):
    dest = request.GET.get("dest")
    sender = request.GET.get("sender")
    message = request.GET.get("message")
    incoming_sms(sender, message, "YO")
    return HttpResponse("OK")

