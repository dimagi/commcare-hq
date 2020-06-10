import re
from typing import TYPE_CHECKING, Optional
from urllib.parse import urljoin

from django.utils.translation import gettext_lazy as _

import attr
import requests
from oauthlib.oauth2 import LegacyApplicationClient
from requests import Session
from requests.auth import AuthBase, HTTPBasicAuth, HTTPDigestAuth
from requests.exceptions import RequestException
from requests_oauthlib import OAuth1, OAuth2Session

from corehq.motech.exceptions import ConfigurationError
from corehq.motech.utils import get_endpoint_url

if TYPE_CHECKING:
    from corehq.motech.models import ConnectionSettings


@attr.s(auto_attribs=True, frozen=True, kw_only=True)
class OAuth1ApiEndpoints:
    """
    Endpoints of a particular OAuth1 API
    """
    # Endpoint for token to identify HQ. e.g. '/oauth/request_token' (Twitter)
    request_token_endpoint: str
    # Endpoint for user to authorize HQ. e.g. '/oauth/authorize'
    authorization_endpoint: str
    # Endpoint to fetch access token. e.g. '/oauth/access_token'
    access_token_endpoint: str


@attr.s(auto_attribs=True, frozen=True, kw_only=True)
class OAuth2ApiSettings:
    """
    Settings and endpoints for an OAuth 2.0 API
    """
    # Pass credentials in Basic Auth header when requesting a token?
    # Otherwise they are passed in the request body.
    pass_credentials_in_header: bool
    # Endpoint to fetch bearer token. e.g. '/uaa/oauth/token' (DHIS2)
    token_endpoint: str
    # Endpoint to refresh bearer token. e.g. '/uaa/oauth/token'
    refresh_endpoint: str


# https://docs.dhis2.org/master/en/developer/html/webapi_authentication.html
dhis2_auth_settings = OAuth2ApiSettings(
    token_endpoint="/uaa/oauth/token",
    refresh_endpoint="/uaa/oauth/token",
    pass_credentials_in_header=True,
)


# https://docs.ipswitch.com/MOVEit/Automation2018/API/REST-API/index.html
moveit_automation_settings = OAuth2ApiSettings(
    token_endpoint="/api/v1/token",
    refresh_endpoint="/api/v1/token",
    pass_credentials_in_header=False,
)


oauth1_api_endpoints = tuple(
    # No integrations using OAuth1 authentication (yet?)
)
oauth2_api_settings = (
    ('dhis2_auth_settings', 'DHIS2 OAuth 2.0'),
    ('moveit_automation_settings', 'MOVEit Automation'),
)
api_auth_settings_choices = [
    (None, _('(Not Applicable)')),
    *oauth1_api_endpoints,
    *oauth2_api_settings,
]


class HTTPBearerAuth(AuthBase):
    def __init__(self, username, plaintext_password):
        self.username = username
        self.password = plaintext_password

    def _find_bearer_base(self, r):
        m = re.compile('https.*/api/v[0-9]+/').match(r.url)
        if m:
            return m.group(0)
        else:
            raise RequestException(None, r, "HTTP endpoint is not not valid for bearer auth")

    def _get_auth_token(self, r):
        token_base = self._find_bearer_base(r)
        token_request_url = urljoin(token_base, "token")

        post_data = {
            "grant_type": "password",
            "username": self.username,
            "password": self.password,
        }

        token_response = requests.post(token_request_url, data=post_data)
        try:
            return token_response.json()['access_token']
        except Exception:
            raise RequestException(
                None, r,
                f"Unable to retrieve access token for request: {token_response.content}"
            )

    def __call__(self, r):
        token = self._get_auth_token(r)
        r.headers["Authorization"] = f"Bearer {token}"
        return r


class AuthManager:

    def get_auth(self) -> Optional[AuthBase]:
        """
        Returns an instance of requests.auth.AuthBase, to be passed to
        an outgoing API request, or None if not applicable.
        """
        return None

    def get_session(self) -> Session:
        """
        Returns an instance of requests.Session. Manages authentication
        tokens, if applicable.
        """
        session = Session()
        session.auth = self.get_auth()
        return session


class BasicAuthManager(AuthManager):

    def __init__(self, username, password):
        self.username = username
        self.password = password

    def get_auth(self):
        return HTTPBasicAuth(self.username, self.password)


class DigestAuthManager(AuthManager):

    def __init__(self, username, password):
        self.username = username
        self.password = password

    def get_auth(self):
        return HTTPDigestAuth(self.username, self.password)


class OAuth1Manager(AuthManager):

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        api_endpoints: OAuth1ApiEndpoints,
        connection_settings: 'ConnectionSettings',
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.api_endpoints = api_endpoints
        self.connection_settings = connection_settings

    @property
    def last_token(self) -> Optional[dict]:
        return self.connection_settings.last_token

    def get_auth(self):
        if not self.last_token:
            raise ConfigurationError(_(
                'OAuth1 authentication workflow has not been followed for '
                f'Connection "{self.connection_settings}"'
            ))

        resource_owner_key = self.last_token['oauth_token']
        resource_owner_secret = self.last_token['oauth_token_secret']
        return OAuth1(
            self.client_id,
            client_secret=self.client_secret,
            resource_owner_key=resource_owner_key,
            resource_owner_secret=resource_owner_secret
        )


class BearerAuthManager(AuthManager):
    """
    Like OAuth 2.0 Password Grant, but doesn't use a client ID or
    client secret.
    """

    def __init__(self, username, password):
        self.username = username
        self.password = password

    def get_auth(self):
        return HTTPBearerAuth(self.username, self.password)


class OAuth2PasswordGrantManager(AuthManager):
    """
    Follows the OAuth 2.0 resource owner password credentials (aka
    password) grant type flow.
    """

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        client_id: str,
        client_secret: str,
        api_settings: OAuth2ApiSettings,
        connection_settings: 'ConnectionSettings',
    ):
        self.base_url = base_url
        self.username = username
        self.password = password
        self.client_id = client_id
        self.client_secret = client_secret
        self.api_settings = api_settings
        self.connection_settings = connection_settings

    @property
    def last_token(self) -> Optional[dict]:
        return self.connection_settings.last_token

    @last_token.setter
    def last_token(self, value: dict):
        """
        Save ``ConnectionSettings.last_token`` whenever it is set or
        refreshed so that it can be reused in the future.
        """
        self.connection_settings.last_token = value
        self.connection_settings.save()

    def get_session(self):

        def set_last_token(token):
            # Used by OAuth2Session
            self.last_token = token

        if not self.last_token:
            client = LegacyApplicationClient(client_id=self.client_id)
            session = OAuth2Session(client=client)
            token_url = get_endpoint_url(
                self.base_url, self.api_settings.token_endpoint,
            )
            if self.api_settings.pass_credentials_in_header:
                auth = HTTPBasicAuth(self.client_id, self.client_secret)
                self.last_token = session.fetch_token(
                    token_url=token_url,
                    username=self.username,
                    password=self.password,
                    auth=auth,
                )
            else:
                self.last_token = session.fetch_token(
                    token_url=token_url,
                    username=self.username,
                    password=self.password,
                    client_id=self.client_id,
                    client_secret=self.client_secret,
                )

        # Return session that refreshes token automatically
        refresh_url = get_endpoint_url(
            self.base_url, self.api_settings.refresh_endpoint,
        )
        refresh_kwargs = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
        }
        return OAuth2Session(
            self.client_id,
            token=self.last_token,
            auto_refresh_url=refresh_url,
            auto_refresh_kwargs=refresh_kwargs,
            token_updater=set_last_token
        )
