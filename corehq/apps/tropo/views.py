import json
from .api import API_ID as TROPO_BACKEND_API_ID
from tropo import Tropo
from corehq.apps.ivr.api import incoming as incoming_call
from corehq.apps.sms.api import incoming as incoming_sms
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
        # Handle when Tropo posts to us to send an SMS
        if "parameters" in session:
            params = session["parameters"]
            if ("_send_sms" in params) and ("numberToDial" in params) and ("msg" in params):
                numberToDial = params["numberToDial"]
                msg = params["msg"]
                t = Tropo()
                t.call(to = numberToDial, network = "SMS")
                t.say(msg)
                return HttpResponse(t.RenderJson())
        # Handle incoming SMS
        phone_number = None
        text = None
        if "from" in session:
            phone_number = session["from"]["id"]
        if "initialText" in session:
            text = session["initialText"]
        if phone_number is not None and len(phone_number) > 1:
            if phone_number[0] == "+":
                phone_number = phone_number[1:]
        incoming_sms(phone_number, text, TROPO_BACKEND_API_ID)
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
        incoming_call(phone_number, TROPO_BACKEND_API_ID)
        #
        t = Tropo()
        t.reject()
        return HttpResponse(t.RenderJson())
    else:
        return HttpResponseBadRequest("Bad Request")


