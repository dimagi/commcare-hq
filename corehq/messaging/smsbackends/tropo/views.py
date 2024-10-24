import json
from datetime import datetime

from django.http import HttpResponse, HttpResponseBadRequest

from corehq.apps.ivr.models import Call
from corehq.apps.sms.api import incoming as incoming_sms
from corehq.apps.sms.models import INCOMING, PhoneNumber
from corehq.apps.sms.util import strip_plus
from corehq.apps.sms.views import IncomingBackendView
from corehq.messaging.smsbackends.tropo.models import SQLTropoBackend


def sms_in(request, backend_id=None):
    """
    Handles tropo messaging requests
    """
    from tropo import Tropo
    if request.method == "POST":
        data = json.loads(request.body.decode('utf-8'))
        session = data["session"]
        # Handle when Tropo posts to us to send an SMS
        if "parameters" in session:
            params = session["parameters"]
            if ("_send_sms" in params) and ("numberToDial" in params) and ("msg" in params):
                numberToDial = params["numberToDial"]
                msg = params["msg"]
                t = Tropo()
                t.call(to=numberToDial, network="SMS")
                t.say(msg)
                return HttpResponse(t.RenderJson(), content_type='application/json')
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
        incoming_sms(phone_number, text, SQLTropoBackend.get_api_id(), backend_id=backend_id)
        t = Tropo()
        t.hangup()
        return HttpResponse(t.RenderJson(), content_type='application/json')
    else:
        return HttpResponseBadRequest("Bad Request")


def ivr_in(request):
    """
    Handles tropo call requests
    """
    from tropo import Tropo
    if request.method == "POST":
        data = json.loads(request.body.decode('utf-8'))
        phone_number = data["session"]["from"]["id"]

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
        return HttpResponse(t.RenderJson(), content_type='application/json')
    else:
        return HttpResponseBadRequest("Bad Request")


class TropoIncomingSMSView(IncomingBackendView):
    urlname = 'tropo_sms'

    @property
    def backend_class(self):
        return SQLTropoBackend

    def post(self, request, api_key, *args, **kwargs):
        return sms_in(request, backend_id=self.backend_couch_id)


class TropoIncomingIVRView(IncomingBackendView):
    urlname = 'tropo_ivr'

    @property
    def backend_class(self):
        return SQLTropoBackend

    def post(self, request, api_key, *args, **kwargs):
        return ivr_in(request)
