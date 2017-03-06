import json

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View
from corehq.apps.analytics.tasks import track_clicked_deploy_on_hubspot, job_candidate_hubspot_update
from corehq.apps.analytics.utils import get_meta


class HubspotClickDeployView(View):
    urlname = 'hubspot_click_deploy'

    def post(self, request, *args, **kwargs):
        meta = get_meta(request)
        track_clicked_deploy_on_hubspot.delay(request.couch_user, request.COOKIES, meta)
        return HttpResponse()


class GreenHouseCandidate(View):
    urlname = 'greenhouse_candidate'

    @csrf_exempt
    def dispatch(self, request, *args, **kwargs):
        super(GreenHouseCandidate, self).dispatch(request=request, args=args, kwargs=kwargs)

    def post(self, request, *args, **kwargs):
        meta = get_meta(request)
        body_unicode = request.body.decode('utf-8')
        data = json.loads(body_unicode)
        try:
            user_emails = data["payload"]["application"]["candidate"]["email_addresses"]
            for user_email in user_emails:
                job_candidate_hubspot_update.delay(user_email["value"])
        except KeyError:
            pass

        return HttpResponse()
