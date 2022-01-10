from django.conf import settings
from django.http import HttpResponseRedirect
from django.urls import reverse

from corehq.apps.oauth.models.gsuite import GoogleApiToken
from corehq.apps.oauth.utils import (
    stringify_credentials,
    load_credentials,
    check_token_exists,
    get_redirect_uri)
from corehq.apps.export.exceptions import InvalidLoginException

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
from google.auth.exceptions import RefreshError


def redirect_oauth_view(request, domain):
    redirect_uri = get_redirect_uri(domain)
    INDEX_URL = 0

    token = check_token_exists(request.user)

    if token is None:
        flow = Flow.from_client_config(
            settings.GOOGLE_OATH_CONFIG,
            settings.GOOGLE_OAUTH_SCOPES,
            redirect_uri=redirect_uri
        )
        # Returns a tuple containing (url, state) and we only want the url
        auth_tuple = flow.authorization_url(prompt='consent')
        return HttpResponseRedirect(auth_tuple[INDEX_URL])
    else:
        credentials = load_credentials(token.token)
        try:
            credentials.refresh(Request())
        # When we lose access to a user's refresh token, we get this refresh error.
        # This will simply have them log into google sheets again to give us another refresh token
        except RefreshError:
            flow = Flow.from_client_config(
                settings.GOOGLE_OATH_CONFIG,
                settings.GOOGLE_OAUTH_SCOPES,
                redirect_uri=redirect_uri
            )
            auth_tuple = flow.authorization_url(prompt='consent')
            return HttpResponseRedirect(auth_tuple[INDEX_URL])
        return HttpResponseRedirect(reverse('google_sheet_view_redirect', args=[domain]))


def call_back_view(request, domain):
    redirect_uri = get_redirect_uri(domain)

    try:
        state = request.GET.get('state', None)

        if not state:
            raise InvalidLoginException

        flow = Flow.from_client_config(
            settings.GOOGLE_OATH_CONFIG,
            settings.GOOGLE_OAUTH_SCOPES,
            redirect_uri=redirect_uri
        )
        flow.redirect_uri = redirect_uri

        # Fetch the token and stringify it
        authorization_response = request.build_absolute_uri()
        flow.fetch_token(authorization_response)
        credentials = flow.credentials
        stringified_token = stringify_credentials(credentials)

        token = GoogleApiToken.objects.get(user=request.user)

        if token is None:
            GoogleApiToken.objects.create(
                user=request.user,
                token=stringified_token
            )
        else:
            token.token = stringified_token
            token.save()

    except InvalidLoginException:
        print("Hello There")

    return HttpResponseRedirect(reverse('google_sheet_view_redirect', args=[domain]))
