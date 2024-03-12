import re
from typing import TYPE_CHECKING, Optional
from urllib.parse import urljoin

from django.utils.translation import gettext_lazy as _

import attr
import requests
from oauthlib.oauth2 import LegacyApplicationClient, BackendApplicationClient
from requests import Session
from requests.auth import AuthBase, HTTPBasicAuth, HTTPDigestAuth
from requests.exceptions import RequestException
from requests_oauthlib import OAuth1, OAuth2Session

from corehq.motech.exceptions import ConfigurationError
from corehq.util.public_only_requests.public_only_requests import make_session_public_only, get_public_only_session

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

    def get_session(self, domain_name: str) -> Session:
        """
        Returns an instance of requests.Session. Manages authentication
        tokens, if applicable.
        """
        session = get_public_only_session(domain_name, src='motech_send_attempt')
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


class OAuth2ClientGrantManager(AuthManager):
    """
    Follows the OAuth 2.0 client credentials grant type flow
    """

    def __init__(
        self,
        base_url: str,
        client_id: str,
        client_secret: str,
        token_url: str,
        refresh_url: str,
        pass_credentials_in_header: bool,
        connection_settings: 'ConnectionSettings',
    ):
        self.base_url = base_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_url = token_url
        self.refresh_url = refresh_url
        self.pass_credentials_in_header = pass_credentials_in_header
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

    def get_session(self, domain_name: str) -> Session:
        # Compare to OAuth2PasswordGrantManager.get_session()

        def set_last_token(token):
            # Used by OAuth2Session
            self.last_token = token

        if not self.last_token or self.last_token.get('refresh_token') is None:
            client = BackendApplicationClient(client_id=self.client_id)
            session = OAuth2Session(client=client)
            if self.pass_credentials_in_header:
                auth = HTTPBasicAuth(self.client_id, self.client_secret)
                self.last_token = session.fetch_token(
                    token_url=self.token_url,
                    auth=auth,
                )
            else:
                self.last_token = session.fetch_token(
                    token_url=self.token_url,
                    client_id=self.client_id,
                    client_secret=self.client_secret,
                    include_client_id=True,
                )

        refresh_kwargs = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
        }
        session = OAuth2Session(
            self.client_id,
            token=self.last_token,
            auto_refresh_url=self.refresh_url,
            auto_refresh_kwargs=refresh_kwargs,
            token_updater=set_last_token
        )
        make_session_public_only(
            session,
            domain_name,
            src='motech_oauth_send_attempt',
        )
        return session


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
        token_url: str,
        refresh_url: str,
        pass_credentials_in_header: bool,
        connection_settings: 'ConnectionSettings',
    ):
        self.base_url = base_url
        self.username = username
        self.password = password
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_url = token_url
        self.refresh_url = refresh_url
        self.pass_credentials_in_header = pass_credentials_in_header
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

    def get_session(self, domain_name: str) -> Session:

        def set_last_token(token):
            # Used by OAuth2Session
            self.last_token = token

        # This adds an extra round trip for all access tokens without
        # refresh tokens. That is not ideal, but is the only way to
        # ensure that we are able to guarantee the token will work
        # without error, or refactoring the way sessions are used across
        # all repeaters.
        if not self.last_token or self.last_token.get('refresh_token') is None:
            client = LegacyApplicationClient(client_id=self.client_id)
            session = OAuth2Session(client=client)
            if self.pass_credentials_in_header:
                auth = HTTPBasicAuth(self.client_id, self.client_secret)
                self.last_token = session.fetch_token(
                    token_url=self.token_url,
                    username=self.username,
                    password=self.password,
                    auth=auth,
                )
            else:
                self.last_token = session.fetch_token(
                    token_url=self.token_url,
                    username=self.username,
                    password=self.password,
                    client_id=self.client_id,
                    client_secret=self.client_secret,
                )

        # Return session that refreshes token automatically
        refresh_kwargs = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
        }
        session = OAuth2Session(
            self.client_id,
            token=self.last_token,
            auto_refresh_url=self.refresh_url,
            auto_refresh_kwargs=refresh_kwargs,
            token_updater=set_last_token
        )
        make_session_public_only(
            session,
            domain_name,
            src='motech_oauth_send_attempt',
        )
        return session


class ApiKeyAuthManager(AuthManager):
    def __init__(self, api_key):
        self.api_key = api_key

    def get_auth(self):
        return CustomValueAuth(self.api_key)


class CustomValueAuth(AuthBase):
    def __init__(self, header_value):
        self.header_value = header_value

    def __call__(self, r):
        if not re.compile('^https').match(r.url):
            raise RequestException(None, r, "Endpoint must be 'HTTPS' to use API Key auth")
        r.headers["Authorization"] = self.header_value
        return r
