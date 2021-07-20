import json

from django.http import Http404, HttpResponse, HttpResponseBadRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from corehq import toggles
from corehq.apps.domain.auth import formplayer_auth
from corehq.apps.enterprise.models import EnterprisePermissions
from corehq.apps.hqadmin.utils import get_django_user_from_session, get_session
from corehq.apps.users.models import CouchUser
from corehq.feature_previews import previews_enabled_for_domain
from corehq.middleware import TimeoutMiddleware
from corehq.toggles import toggles_enabled_for_user, toggles_enabled_for_domain


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
        try:
            data = json.loads(request.body.decode('utf-8'))
        except ValueError:
            return HttpResponseBadRequest()

        if not data or not isinstance(data, dict):
            return HttpResponseBadRequest()

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
        return JsonResponse({
            'username': user.username,
            'djangoUserId': user.pk,
            'superUser': user.is_superuser,
            'authToken': None,
            'domains': list(domains),
            'anonymous': False,
            'enabled_toggles': list(enabled_toggles),
            'enabled_previews': list(previews_enabled_for_domain(domain))
        })
