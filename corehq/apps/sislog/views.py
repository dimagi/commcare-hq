from django.http import HttpResponse
from corehq.apps.sms.api import incoming as incoming_sms

def sms_in(request):
    """
    msisdn - the number (in international format, without leading plus) of the person sending the sms
    sn - the number the sms was sent to
    msg - the message
    """
    msisdn = request.GET.get("msisdn", None)
    sn = request.GET.get("sn", None)
    msg = request.GET.get("msg", None)
    if msisdn is None or msg is None:
        return HttpResponse(status=400)
    else:
        incoming_sms(msisdn, msg, "SISLOG")
        return HttpResponse()

