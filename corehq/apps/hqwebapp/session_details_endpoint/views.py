from __future__ import absolute_import
from __future__ import unicode_literals
import json
import six

from django.http import HttpResponseBadRequest, Http404, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from corehq.apps.domain.auth import formplayer_auth
from corehq.apps.hqadmin.utils import get_django_user_from_session_key
from corehq.apps.users.models import CouchUser


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
        # print('SessionDetailsView.post')
        try:
            data = json.loads(request.body.decode('utf-8'))
        except ValueError:
            raise
            # return HttpResponseBadRequest()

        if not data or not isinstance(data, dict):
            return HttpResponseBadRequest()

        session_id = data.get('sessionId', None)
        if not session_id:
            return HttpResponseBadRequest()

        # print(session_id)
        user = get_django_user_from_session_key(session_id)
        # print(user)
        if user:
            couch_user = CouchUser.get_by_username(user.username)
            if not couch_user:
                raise Http404
        else:
            raise Http404

        return JsonResponse({
            'username': user.username,
            'djangoUserId': user.pk,
            'superUser': user.is_superuser,
            'authToken': None,
            'domains': couch_user.domains,
            'anonymous': False
        })
