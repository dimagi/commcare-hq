from __future__ import absolute_import
from __future__ import unicode_literals
import json
from django.http import HttpResponseBadRequest, Http404, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from rest_framework.authtoken.models import Token
from corehq.apps.hqadmin.utils import get_django_user_from_session_key
from corehq.apps.users.models import CouchUser
from corehq.toggles import ANONYMOUS_WEB_APPS_USAGE
from corehq.util.hmac_request import validate_request_hmac


@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(validate_request_hmac('FORMPLAYER_INTERNAL_AUTH_KEY', ignore_if_debug=True), name='dispatch')
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
            data = json.loads(request.body)
        except ValueError:
            return HttpResponseBadRequest()

        if not data or not isinstance(data, dict):
            return HttpResponseBadRequest()

        session_id = data.get('sessionId', None)
        domain = data.get('domain', None)
        if not session_id:
            return HttpResponseBadRequest()

        auth_token = None
        anonymous = False
        user = get_django_user_from_session_key(session_id)
        if user:
            couch_user = CouchUser.get_by_username(user.username)
            if not couch_user:
                raise Http404
        elif domain and ANONYMOUS_WEB_APPS_USAGE.enabled(domain):
            user, couch_user, auth_token = self._get_anonymous_user_details(domain)
            anonymous = True
        else:
            raise Http404

        return JsonResponse({
            'username': user.username,
            'djangoUserId': user.pk,
            'superUser': user.is_superuser,
            'authToken': auth_token,
            'domains': couch_user.domains,
            'anonymous': anonymous
        })

    def _get_anonymous_user_details(self, domain):
        couch_user = CouchUser.get_anonymous_mobile_worker(domain)
        if not couch_user:
            raise Http404
        user = couch_user.get_django_user()
        try:
            auth_token = user.auth_token.key
        except Token.DoesNotExist:
            raise Http404  # anonymous user must have an auth token
        return user, couch_user, auth_token
