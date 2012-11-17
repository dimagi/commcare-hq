import json
from .api import API_ID as TROPO_BACKEND_API_ID
from tropo import Tropo
from corehq.apps.ivr.api import incoming as incoming_call
from corehq.apps.sms.api import incoming as incoming_sms
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from corehq.apps.sms.mixin import VerifiedNumber
from corehq.apps.sms.models import CallLog, INCOMING, OUTGOING
from datetime import datetime

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
        ####
        
        # TODO: Implement tropo as an ivr backend. In the meantime, just log the call.
        
        cleaned_number = phone_number
        if cleaned_number is not None and len(cleaned_number) > 0 and cleaned_number[0] == "+":
            cleaned_number = cleaned_number[1:]
        
        # Try to look up the verified number entry
        v = VerifiedNumber.view("sms/verified_number_by_number",
            key=cleaned_number,
            include_docs=True
        ).one()
        
        # If none was found, try to match only the last digits of numbers in the database
        if v is None:
            v = VerifiedNumber.view("sms/verified_number_by_suffix",
                key=cleaned_number,
                include_docs=True
            ).one()
        
        # Save the call entry
        msg = CallLog(
            phone_number    = cleaned_number,
            direction       = INCOMING,
            date            = datetime.utcnow(),
            backend_api     = TROPO_BACKEND_API_ID
        )
        if v is not None:
            msg.domain = v.domain
            msg.couch_recipient_doc_type = v.owner_doc_type
            msg.couch_recipient = v.owner_id
        msg.save()
        
        ####
        t = Tropo()
        t.reject()
        return HttpResponse(t.RenderJson())
    else:
        return HttpResponseBadRequest("Bad Request")


