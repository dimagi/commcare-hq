from django.conf import settings
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.translation import gettext as _

from corehq.apps.oauth_integrations.models import GoogleApiToken
from corehq.apps.oauth_integrations.utils import (
    stringify_credentials,
    load_credentials,
    get_token,
)
from corehq.apps.export.exceptions import InvalidLoginException

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
from google.auth.exceptions import RefreshError


def redirect_oauth_view(request, domain):
    redirect_uri = request.build_absolute_uri(reverse("google_sheet_oauth_callback"))
    token = get_token(request.user)

    if token is None:
        return HttpResponseRedirect(get_url_from_google(redirect_uri))
    else:
        credentials = load_credentials(token.token)
        try:
            token.token = stringify_credentials(refresh_credentials(credentials))
            token.save()
        # When we lose access to a user's refresh token, we get this refresh error.
        # This will simply have them log into google sheets again to give us another refresh token
        except RefreshError:
            return HttpResponseRedirect(get_url_from_google(redirect_uri))
        #replace with google sheet view
        return HttpResponseRedirect("placeholder.com")


def refresh_credentials(credentials, user):
    return credentials.refresh(Request())


def get_url_from_google(redirect_uri):
    INDEX_URL = 0
    flow = Flow.from_client_config(
        settings.GOOGLE_OATH_CONFIG,
        settings.GOOGLE_OAUTH_SCOPES,
        redirect_uri=redirect_uri
    )
    # Returns a tuple containing (url, state) and we only want the url
    auth_tuple = flow.authorization_url(prompt='consent')
    return auth_tuple[INDEX_URL]


def call_back_view(request, domain):
    redirect_uri = request.build_absolute_uri(reverse("google_sheet_oauth_callback"))

    try:
        check_state(request)

        flow = Flow.from_client_config(
            settings.GOOGLE_OATH_CONFIG,
            settings.GOOGLE_OAUTH_SCOPES,
            redirect_uri=redirect_uri
        )
        flow.redirect_uri = redirect_uri

        # Fetch the token and stringify it
        stringified_token = get_token_from_google(request, flow)

        token = get_token(request.user)

        if not token:
            GoogleApiToken.objects.create(
                user=request.user,
                token=stringified_token
            )
        else:
            token.token = stringified_token
            token.save()

    except InvalidLoginException:
        messages.error(request, _("Something went wrong when trying to sign you in to Google. Please try again."))

    #replace with google sheet view
    return HttpResponseRedirect("placeholder.com")


def check_state(request):
    state = request.GET.get('state', None)

    if not state:
        raise InvalidLoginException


def get_token_from_google(request, flow):
    authorization_response = request.build_absolute_uri()
    flow.fetch_token(authorization_response)
    credentials = flow.credentials
    return stringify_credentials(credentials)
