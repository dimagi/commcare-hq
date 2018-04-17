from __future__ import absolute_import
from __future__ import unicode_literals
import hashlib
import hmac
import json
import six

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View
from django.conf import settings

from corehq.apps.analytics.tasks import (
    track_clicked_deploy_on_hubspot, track_job_candidate_on_hubspot, HUBSPOT_COOKIE
)
from corehq.apps.analytics.utils import get_meta


class HubspotClickDeployView(View):
    urlname = 'hubspot_click_deploy'

    def post(self, request, *args, **kwargs):
        meta = get_meta(request)
        track_clicked_deploy_on_hubspot.delay(request.couch_user, request.COOKIES.get(HUBSPOT_COOKIE), meta)
        return HttpResponse()


class GreenhouseCandidateView(View):
    urlname = 'greenhouse_candidate'

    @csrf_exempt
    def dispatch(self, request, *args, **kwargs):
        return super(GreenhouseCandidateView, self).dispatch(request=request, args=args, kwargs=kwargs)

    def post(self, request, *args, **kwargs):
        digester = hmac.new(
            settings.GREENHOUSE_API_KEY.encode('utf-8')
            if isinstance(settings.GREENHOUSE_API_KEY, six.text_type) else settings.GREENHOUSE_API_KEY,
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
