import json
from tropo import Tropo
from corehq.apps.ivr.api import incoming
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def tropo(request, domain):
    if request.method == "POST":
        data = json.loads(request.raw_post_data)
        phone_number = data["session"]["from"]["id"]
        #
        incoming(domain, phone_number)
        #
        t = Tropo()
        t.reject()
        return HttpResponse(t.RenderJson())
    else:
        return HttpResponseBadRequest("Bad Request")

