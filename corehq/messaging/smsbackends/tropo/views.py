from __future__ import absolute_import
from __future__ import unicode_literals
import json
from .models import SQLTropoBackend
from tropo import Tropo
from corehq.apps.sms.api import incoming as incoming_sms
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from corehq.apps.ivr.models import Call
from corehq.apps.sms.models import INCOMING, PhoneNumber
from datetime import datetime
from corehq.apps.sms.util import strip_plus


@csrf_exempt
def sms_in(request):
    """
    Handles tropo messaging requests
    """
    if request.method == "POST":
        data = json.loads(request.body)
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
        incoming_sms(phone_number, text, SQLTropoBackend.get_api_id())
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
        data = json.loads(request.body)
        phone_number = data["session"]["from"]["id"]
        # TODO: Implement tropo as an ivr backend. In the meantime, just log the call.

        if phone_number:
            cleaned_number = strip_plus(phone_number)
            v = PhoneNumber.by_extensive_search(cleaned_number)
        else:
            v = None

        # Save the call entry
        msg = Call(
            phone_number=cleaned_number,
            direction=INCOMING,
            date=datetime.utcnow(),
            backend_api=SQLTropoBackend.get_api_id(),
        )
        if v is not None:
            msg.domain = v.domain
            msg.couch_recipient_doc_type = v.owner_doc_type
            msg.couch_recipient = v.owner_id
        msg.save()

        t = Tropo()
        t.reject()
        return HttpResponse(t.RenderJson())
    else:
        return HttpResponseBadRequest("Bad Request")
