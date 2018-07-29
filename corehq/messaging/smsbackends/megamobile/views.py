from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.sms.api import incoming as incoming_sms
from corehq.messaging.smsbackends.megamobile.models import SQLMegamobileBackend
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
def sms_in(request):
    pid = request.GET.get("pid", None)
    msg = request.GET.get("msg", None)
    cel = request.GET.get("cel", None)
    tcs = request.GET.get("tcs", None)

    phone_number = "%s%s" % ("63", cel)
    incoming_sms(
        phone_number,
        msg,
        SQLMegamobileBackend.get_api_id()
    )
    return HttpResponse("")
