import hashlib
import hmac
import json
import requests

from gettext import gettext

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic import View

from corehq.apps.analytics.tasks import (
    HUBSPOT_COOKIE,
    track_clicked_deploy_on_hubspot,
    track_job_candidate_on_hubspot,
)
from corehq.apps.analytics.utils import (
    get_meta,
    get_client_ip_from_request,
    log_response,
)


class HubspotClickDeployView(View):
    urlname = 'hubspot_click_deploy'

    def post(self, request, *args, **kwargs):
        meta = get_meta(request)
        if hasattr(request, 'couch_user'):
            track_clicked_deploy_on_hubspot.delay(request.couch_user.get_id,
                                                  request.COOKIES.get(HUBSPOT_COOKIE), meta)
        return HttpResponse()


class GreenhouseCandidateView(View):
    urlname = 'greenhouse_candidate'

    @csrf_exempt
    def dispatch(self, request, *args, **kwargs):
        return super(GreenhouseCandidateView, self).dispatch(request=request, args=args, kwargs=kwargs)

    def post(self, request, *args, **kwargs):
        digester = hmac.new(
            settings.GREENHOUSE_API_KEY.encode('utf-8')
            if isinstance(settings.GREENHOUSE_API_KEY, str) else settings.GREENHOUSE_API_KEY,
            request.body, hashlib.sha256
        )
        calculated_signature = digester.hexdigest()

        signature_header = request.META.get('HTTP_SIGNATURE', '').split()
        if len(signature_header) == 2:
            signature_from_request = signature_header[1]
        else:
            return HttpResponse()
        if str(calculated_signature) == str(signature_from_request):
            body_unicode = request.body.decode('utf-8')
            data = json.loads(body_unicode)
            try:
                user_emails = data["payload"]["application"]["candidate"]["email_addresses"]
                for user_email in user_emails:
                    track_job_candidate_on_hubspot.delay(user_email["value"])
            except KeyError:
                pass

        return HttpResponse()


@require_POST
def submit_hubspot_cta_form(request):
    form_data = {data: value[0] for data, value in dict(request.POST).items()}
    form_id = form_data.pop('hubspot_form_id')
    page_url = form_data.pop('page_url')
    page_name = form_data.pop('page_name')

    hubspot_cookie = request.COOKIES.get(HUBSPOT_COOKIE)
    form_data['hs_context'] = json.dumps({
        "hutk": hubspot_cookie,
        "ipAddress": get_client_ip_from_request(request),
        "pageUrl": page_url,
        "pageName": page_name,
    })

    hubspot_id = settings.ANALYTICS_IDS.get('HUBSPOT_API_ID')
    if not hubspot_id:
        return JsonResponse({
            "success": False,
            "message": gettext("No hubspot API ID is present."),
        })

    url = f"https://forms.hubspot.com/uploads/form/v2/{hubspot_id}/{form_id}"
    response = requests.post(url, data=form_data)
    log_response('HS', form_data, response)
    response.raise_for_status()

    return JsonResponse({
        "success": True,
    })
