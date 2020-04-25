import logging
from typing import Optional

from django.conf import settings

import requests
from oauthlib.oauth2 import LegacyApplicationClient
from requests.auth import HTTPBasicAuth, HTTPDigestAuth
from requests.structures import CaseInsensitiveDict
from requests_oauthlib import OAuth2Session

from dimagi.utils.logging import notify_exception

from corehq.apps.hqwebapp.tasks import send_mail_async
from corehq.motech.const import (
    AUTH_TYPES,
    BASIC_AUTH,
    DIGEST_AUTH,
    OAUTH1,
    OAUTH2_BEARER,
    REQUEST_TIMEOUT,
)
from corehq.motech.models import ApiAuthSettings, RequestLog
from corehq.motech.utils import pformat_json


def log_request(func):

    def request_wrapper(self, *args, **kwargs):
        log_level = logging.INFO
        request_error = ''
        response_status = None
        response_body = ''
        try:
            response = func(self, *args, **kwargs)
            response_status = response.status_code
            response_body = response.content
        except Exception as err:
            log_level = logging.ERROR
            request_error = str(err)
            if getattr(err, 'response', None) is not None:
                response_status = err.response.status_code
                response_body = pformat_json(err.response.text)
            raise
        else:
            return response
        finally:
            # args will be Requests method, url, and optionally params, data or json.
            # kwargs may include Requests method kwargs and raise_for_status.
            kwargs.pop('raise_for_status', None)
            RequestLog.log(
                log_level,
                self.domain_name,
                self.payload_id,
                request_error,
                response_status,
                response_body,
                *args,
                **kwargs
            )

    return request_wrapper


class Requests(object):
    """
    Wraps the requests library to simplify use with JSON REST APIs.

    Sets auth headers automatically, and requests JSON responses by
    default.

    To maintain a session of authenticated non-API requests, use
    Requests as a context manager.
    """

    def __init__(
        self,
        domain_name: str,
        base_url: str,
        username: str = '',
        password: str = '',
        *,
        verify: bool = True,
        auth_type: Optional[str] = BASIC_AUTH,
        api_auth_settings: Optional[ApiAuthSettings] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        last_token: Optional[dict] = None,
        notify_addresses: Optional[list] = None,
        payload_id: Optional[str] = None,
    ):
        """
        Initialise instance

        :param domain_name: Domain to store logs under
        :param base_url: Remote API base URL
        :param username: Remote API username.
        :param password: Remote API plaintext password.
        :param verify: Verify SSL certificate?
        :param auth_type: Type of web service authentication to use
        :param api_auth_settings: An object of URLs to use for OAuth1
            and OAuth 2.0 authentication workflows
        :param client_id: OAuth1 client key / OAuth 2.0 client ID
        :param client_secret: OAuth1 & OAuth 2.0 client secret
        :param last_token: Can be used for OAuth1 so that the user is
            only asked to authorize HQ once
        :param notify_addresses: A list of email addresses to notify of
            errors.
        :param payload_id: The ID of the case or form submission
            associated with this request
        """
        assert (
            auth_type is None
            or auth_type in {value for value, name in AUTH_TYPES}
        ), f"Unknown auth_type {auth_type!r}."

        if auth_type in (OAUTH1, OAUTH2_BEARER):
            assert api_auth_settings, \
                f"api_auth_settings is required for auth_type {auth_type!r}"

        self.domain_name = domain_name
        self.base_url = base_url
        self.username = username
        self.password = password
        self.verify = verify
        self.auth_type = auth_type
        self.api_auth_settings = api_auth_settings
        self.client_id = client_id
        self.client_secret = client_secret
        self.last_token = {} if last_token is None else last_token
        self.notify_addresses = [] if notify_addresses is None else notify_addresses
        self.payload_id = payload_id

        self._session = None

    def __enter__(self):
        self._session = self._get_new_session()
        return self

    def __exit__(self, *args):
        self._session.close()
        self._session = None

    def _get_new_session(self):
        if self.auth_type in (None, BASIC_AUTH, DIGEST_AUTH, OAUTH1):
            return requests.Session()
        if self.auth_type == OAUTH2_BEARER:
            # Uses the resource owner password credentials grant type
            if not self.last_token:
                client = LegacyApplicationClient(client_id=self.client_id)
                session = OAuth2Session(client=client)
                token_url = self.get_url(self.api_auth_settings.token_url)
                if self.api_auth_settings.pass_credentials_in_header:
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
            refresh_url = self.get_url(self.api_auth_settings.refresh_url)
            refresh_kwargs = {
                'client_id': self.client_id,
                'client_secret': self.client_secret,
            }
            return OAuth2Session(
                self.client_id,
                token=self.last_token,
                auto_refresh_url=refresh_url,
                auto_refresh_kwargs=refresh_kwargs,
                token_updater=self.set_last_token
            )

    def set_last_token(self, token):
        """Used by OAuth2Session"""
        self.last_token = token

    @log_request
    def send_request(self, method, *args, **kwargs):
        raise_for_status = kwargs.pop('raise_for_status', False)
        if not self.verify:
            kwargs['verify'] = False
        kwargs.setdefault('timeout', REQUEST_TIMEOUT)
        # TODO: Python >= 3.8
        # if 'auth' not in kwargs and auth := self.get_auth():
        #     kwargs['auth'] = auth
        if 'auth' not in kwargs:
            auth = self.get_auth()
            if auth:
                # We use a session instead of auth for OAuth 2.0
                kwargs['auth'] = auth
        if self._session:
            response = self._session.request(method, *args, **kwargs)
        else:
            # Mimics the behaviour of requests.api.request()
            with requests.Session() as session:
                response = session.request(method, *args, **kwargs)
        if raise_for_status:
            response.raise_for_status()
        return response

    def get_url(self, uri):
        return '/'.join((self.base_url.rstrip('/'), uri.lstrip('/')))

    def get_auth(self):
        if self.auth_type is None:
            return None
        if self.auth_type == BASIC_AUTH:
            return (self.username, self.password)
        if self.auth_type == DIGEST_AUTH:
            return HTTPDigestAuth(self.username, self.password)
        if self.auth_type == OAUTH1:
            # TODO: OAuth1 workflow must be implemented in
            #       ConnectionSettingsView to set ConnectionSettings.last_token
            raise NotImplementedError(
                'OAuth1 authentication workflow is not yet supported'
            )
            # # Use saved token from ConnectionSettings
            # resource_owner_key = self.last_token['oauth_token']
            # resource_owner_secret = self.last_token['oauth_token_secret']
            # return OAuth1(
            #     self.client_id,
            #     client_secret=self.client_secret,
            #     resource_owner_key=resource_owner_key,
            #     resource_owner_secret=resource_owner_secret
            # )
        if self.auth_type == OAUTH2_BEARER:
            return None

    def delete(self, uri, **kwargs):
        kwargs.setdefault('headers', {'Accept': 'application/json'})
        return self.send_request('DELETE', self.get_url(uri), **kwargs)

    def get(self, uri, *args, **kwargs):
        kwargs.setdefault('headers', {'Accept': 'application/json'})
        kwargs.setdefault('allow_redirects', True)
        return self.send_request('GET', self.get_url(uri), *args, **kwargs)

    def post(self, uri, data=None, json=None, *args, **kwargs):
        kwargs.setdefault('headers', {
            'Content-type': 'application/json',
            'Accept': 'application/json'
        })
        return self.send_request('POST', self.get_url(uri), *args,
                                 data=data, json=json, **kwargs)

    def put(self, uri, data=None, json=None, *args, **kwargs):
        kwargs.setdefault('headers', {
            'Content-type': 'application/json',
            'Accept': 'application/json'
        })
        return self.send_request('PUT', self.get_url(uri), *args,
                                 data=data, json=json, **kwargs)

    def simple_post(self, absolute_url, data, *, headers=None, timeout=60):
        """
        Used by Repeater base class and to test connections.

        Takes advantage of logging, but does not prepend the base URL,
        and allows the caller easily to override headers and timeout.
        """
        if isinstance(data, str):
            data = data.encode('utf-8')
        default_headers = CaseInsensitiveDict({
            "content-type": "text/xml",
            "content-length": str(len(data)),
        })
        if headers:
            default_headers.update(headers)
        kwargs = {
            "headers": default_headers,
            "timeout": timeout,
        }
        # Use `send_request()` instead of `post()` so that we can pass
        # the absolute URL
        return self.send_request('POST', absolute_url, data=data, **kwargs)

    def notify_exception(self, message=None, details=None):
        self.notify_error(message, details)
        notify_exception(None, message, details)

    def notify_error(self, message, details=None):
        if not self.notify_addresses:
            return
        message_lines = [
            message,
            f'Project space: {self.domain_name}',
            f'Remote API base URL: {self.base_url}',
            f'Remote API username: {self.username}',
        ]
        if self.payload_id:
            message_lines.append(f'Payload ID: {self.payload_id}')
        if details:
            message_lines.extend(['', '', details])
        send_mail_async.delay(
            'MOTECH Error',
            '\r\n'.join(message_lines),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=self.notify_addresses,
        )


def parse_request_exception(err):
    """
    Parses an instance of RequestException and returns a request
    string and response string tuple
    """
    err_request = '{method} {url}\n\n{body}'.format(
        method=err.request.method,
        url=err.request.url,
        body=err.request.body
    ) if err.request.body else ' '.join((err.request.method, err.request.url))
    if err.response:
        err_content = pformat_json(err.response.content)  # pformat_json returns non-JSON values unchanged
        err_response = '\n\n'.join((str(err), err_content))
    else:
        err_response = str(err)
    return err_request, err_response
