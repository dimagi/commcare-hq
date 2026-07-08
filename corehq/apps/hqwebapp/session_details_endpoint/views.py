import json
from datetime import datetime

from django.http import Http404, HttpResponse, HttpResponseBadRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from corehq import toggles
from corehq.apps.app_manager.models import PublicFormSession
from corehq.apps.domain.auth import formplayer_auth
from corehq.apps.enterprise.models import EnterprisePermissions
from corehq.apps.hqadmin.utils import get_django_user_from_session, get_session
from corehq.apps.users.models import CouchUser
from corehq.feature_previews import previews_enabled_for_domain
from corehq.middleware import TimeoutMiddleware
from corehq.toggles import toggles_enabled_for_user, toggles_enabled_for_domain
from corehq.util.metrics import (
    limit_domains,
    metrics_histogram
)


@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(formplayer_auth, name='dispatch')
class SessionDetailsView(View):
    """
    Internal API to allow formplayer to get the Django user ID
    from the session key.

    Authentication is done by HMAC signing of the request body:

        secret = settings.FORMPLAYER_INTERNAL_AUTH_KEY
        data = '{"session_id": "123"}'
        digest = base64.b64encode(hmac.new(secret, data, hashlib.sha256).digest())
        requests.post(url, data=data, headers={'X-MAC-DIGEST': digest})
    """
    urlname = 'session_details'
    http_method_names = ['post']

    def post(self, request, *args, **kwargs):
        start_time = datetime.now()
        try:
            data = json.loads(request.body.decode('utf-8'))
        except ValueError:
            return HttpResponseBadRequest()

        if not data or not isinstance(data, dict):
            return HttpResponseBadRequest()

        public_session_key = data.get('publicSessionKey')
        if public_session_key:
            return self._public_session_details(public_session_key, start_time)

        session_id = data.get('sessionId', None)
        if not session_id:
            return HttpResponseBadRequest()

        session = get_session(session_id)
        user = get_django_user_from_session(session)
        if user:
            couch_user = CouchUser.get_by_username(user.username)
            if not couch_user:
                raise Http404
        else:
            raise Http404

        domain = data.get('domain')
        if domain and toggles.DISABLE_WEB_APPS.enabled(domain):
            return HttpResponse('Service Temporarily Unavailable', content_type='text/plain', status=503)

        # reset the session's expiry if there's some formplayer activity
        secure_session = session.get('secure_session')
        TimeoutMiddleware.update_secure_session(session, secure_session, couch_user, domain=domain)
        session.save()

        domains = set()
        for member_domain in couch_user.domains:
            domains.add(member_domain)
            domains.update(EnterprisePermissions.get_domains(member_domain))

        enabled_toggles = toggles_enabled_for_user(user.username) | toggles_enabled_for_domain(domain)
        enabled_previews = previews_enabled_for_domain(domain)
        self._record_processing_time(start_time, domain)
        return JsonResponse({
            'username': user.username,
            'djangoUserId': user.pk,
            'superUser': user.is_superuser,
            'authToken': session_id,
            'domains': list(domains),
            'public': False,
            'enabled_toggles': list(sorted(enabled_toggles)),
            'enabled_previews': list(enabled_previews)
        })

    def _public_session_details(self, public_session_key, start_time):
        session = PublicFormSession.get_active_by_key(public_session_key)
        if session is None:
            raise Http404

        domain = session.public_webform.domain
        if toggles.DISABLE_WEB_APPS.enabled(domain):
            return HttpResponse('Service Temporarily Unavailable', content_type='text/plain', status=503)

        self._record_processing_time(start_time, domain)
        return JsonResponse({
            'username': session.session_username,
            'djangoUserId': None,
            'superUser': False,
            'authToken': str(public_session_key),
            'domains': [domain],
            'public': True,
            'enabled_toggles': list(sorted(toggles_enabled_for_domain(domain))),
            'enabled_previews': list(previews_enabled_for_domain(domain)),
        })

    @staticmethod
    def _record_processing_time(start_time, domain):
        elapsed_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        metrics_histogram("commcare.session_details.processing_time",
                      elapsed_ms,
                      bucket_tag='duration_bucket',
                      buckets=(250, 1000, 3000),
                      bucket_unit='ms',
                      tags={'domain': limit_domains(domain)})
