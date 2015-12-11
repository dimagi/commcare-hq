from django.http import HttpResponse
from django.views.generic import View
from corehq.apps.analytics.tasks import track_clicked_deploy_on_hubspot
from corehq.apps.analytics.utils import get_meta


class HubspotClickDeployView(View):
    urlname = 'hubspot_click_deploy'

    def post(self, request, *args, **kwargs):
        meta = get_meta(request)
        track_clicked_deploy_on_hubspot.delay(request.couch_user, request.COOKIES, meta)
        return HttpResponse()
