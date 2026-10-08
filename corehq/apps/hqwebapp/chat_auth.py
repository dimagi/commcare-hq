"""Issue OCS widget credentials after checking the user's monthly allowance."""

import requests
from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden
from django.views.decorators.http import require_POST

from corehq.apps.domain.decorators import login_required
from corehq.apps.hqwebapp.chat_quota import UNLIMITED, get_chatbot_message_quota
from corehq.apps.hqwebapp.chat_usage import fetch_chat_usage_from_ocs
from corehq.apps.hqwebapp.exceptions import ChatTokenUnavailable, ChatUsageUnavailable

_TOKEN_URL = 'https://www.openchatstudio.com/o/token/'


@login_required
@require_POST
def chat_token(request):
    couch_user = getattr(request, 'couch_user')

    try:
        limit = get_chatbot_message_quota(couch_user)
        if limit == 0:
            return HttpResponseForbidden()
        if limit != UNLIMITED:
            if fetch_chat_usage_from_ocs(couch_user.user_id) >= limit:
                return HttpResponseForbidden()
        token = _mint_widget_token()
    except (ChatUsageUnavailable, ChatTokenUnavailable):
        return HttpResponse(status=503)
    return HttpResponse(token, content_type='text/plain')


def _mint_widget_token():
    if not (settings.OCS_OAUTH_CLIENT_ID and settings.OCS_OAUTH_CLIENT_SECRET):
        raise ChatTokenUnavailable('Missing OCS OAuth configuration')
    try:
        response = requests.post(
            _TOKEN_URL,
            data={
                'grant_type': 'client_credentials',
                'client_id': settings.OCS_OAUTH_CLIENT_ID,
                'client_secret': settings.OCS_OAUTH_CLIENT_SECRET,
                'scope': 'chat:start',
            },
            timeout=(5, 15),
        )
        response.raise_for_status()
        return response.json()['access_token']
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        raise ChatTokenUnavailable('OCS widget credential unavailable') from exc
