from corehq.apps.sms.api import incoming as incoming_sms
from corehq.messaging.smsbackends.megamobile.models import SQLMegamobileBackend
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def sms_in(request):
    pid = request.GET.get("pid", None)
    msg = request.GET.get("msg", None)
    cel = request.GET.get("cel", None)
    tcs = request.GET.get("tcs", None)

    megamobile_attrs = {
        "megamobile_pid" : pid,
        "megamobile_tcs" : tcs,
    }

    phone_number = "%s%s" % ("63", cel)
    incoming_sms(
        phone_number,
        msg,
        SQLMegamobileBackend.get_api_id(),
        backend_attributes=megamobile_attrs
    )
    return HttpResponse("")

