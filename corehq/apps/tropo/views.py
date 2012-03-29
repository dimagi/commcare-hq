import json
from tropo import Tropo
from corehq.apps.ivr.api import incoming as incoming_call
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def sms_in(request):
    """
    Handles tropo messaging requests
    """
    if request.method == "POST":
        data = json.loads(request.raw_post_data)
        session = data["session"]
        if "parameters" in session:
            params = session["parameters"]
            if ("_send_sms" in params) and ("numberToDial" in params) and ("msg" in params):
                numberToDial = params["numberToDial"]
                msg = params["msg"]
                t = Tropo()
                t.call(to = numberToDial, network = "SMS")
                t.say(msg)
                return HttpResponse(t.RenderJson())
        t = Tropo()
        t.hangup()
        return HttpResponse(t.RenderJson())
    else:
        return HttpResponseBadRequest("Bad Request")

@csrf_exempt
def ivr_in(request):
    """
    Handles tropo call requests
    """
    if request.method == "POST":
        data = json.loads(request.raw_post_data)
        phone_number = data["session"]["from"]["id"]
        #
        incoming_call(phone_number)
        #
        t = Tropo()
        t.reject()
        return HttpResponse(t.RenderJson())
    else:
        return HttpResponseBadRequest("Bad Request")


