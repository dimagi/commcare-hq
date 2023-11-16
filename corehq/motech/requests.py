import logging
from functools import wraps
from typing import Callable, Optional

from django.conf import settings
from django.utils.translation import gettext as _

from requests import HTTPError
from requests.structures import CaseInsensitiveDict

from dimagi.utils.logging import notify_exception

from corehq.apps.hqwebapp.tasks import send_mail_async
from corehq.motech.auth import AuthManager, BasicAuthManager
from corehq.motech.const import (
    REQUEST_DELETE,
    REQUEST_POST,
    REQUEST_PUT,
    REQUEST_TIMEOUT,
)
from corehq.motech.models import RequestLog, RequestLogEntry
from corehq.motech.utils import (
    get_endpoint_url,
    pformat_json,
    unpack_request_args,
)
from corehq.util.metrics import metrics_counter
from corehq.util.urlvalidate.urlvalidate import (
    InvalidURL,
    PossibleSSRFAttempt,
    validate_user_input_url,
)
from corehq.util.view_utils import absolute_reverse


def log_request(self, func, logger):

    @wraps(func)
    def request_wrapper(method, url, *args, **kwargs):
        log_level = logging.INFO
        request_error = ''
        response_status = None
        response_headers = {}
        response_body = ''
        try:
            response = func(method, url, *args, **kwargs)
            response_status = response.status_code
            response_headers = response.headers
            response_body = response.content
        except Exception as err:
            log_level = logging.ERROR
            request_error = str(err)
            if getattr(err, 'response', None) is not None:
                response_status = err.response.status_code
                response_headers = err.response.headers
                response_body = pformat_json(err.response.text)
            raise
        else:
            return response
        finally:
            params, data, headers = unpack_request_args(method, args, kwargs)
            entry = RequestLogEntry(
                domain=self.domain_name,
                payload_id=self.payload_id,
                method=method,
                url=url,
                headers=headers,
                params=params,
                data=data,
                error=request_error,
                response_status=response_status,
                response_headers=response_headers,
                response_body=response_body,
            )
            logger(log_level, entry)

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
        base_url: Optional[str],
        *,
        verify: bool = True,
        auth_manager: AuthManager,
        notify_addresses: Optional[list] = None,
        payload_id: Optional[str] = None,
        logger: Optional[Callable] = None,
    ):
        """
        Initialise instance

        :param domain_name: Domain to store logs under
        :param base_url: Remote API base URL
        :param verify: Verify SSL certificate?
        :param auth_manager: AuthManager instance to manage
            authentication
        :param notify_addresses: A list of email addresses to notify of
            errors.
        :param payload_id: The ID of the case or form submission
            associated with this request
        :param logger: function called after a request has been sent:
                        `logger(log_level, log_entry: RequestLogEntry)`
        """
        self.domain_name = domain_name
        self.base_url = base_url
        self.verify = verify
        self.auth_manager = auth_manager
        self.notify_addresses = notify_addresses if notify_addresses else []
        self.payload_id = payload_id
        self.logger = logger or RequestLog.log
        self.send_request = log_request(self, self.send_request_unlogged, self.logger)
        self._session = None

    def __enter__(self):
        self._session = self.auth_manager.get_session(self.domain_name)
        return self

    def __exit__(self, *args):
        self._session.close()
        self._session = None

    def send_request_unlogged(self, method, url, *args, **kwargs):
        raise_for_status = kwargs.pop('raise_for_status', False)
        if not self.verify:
            kwargs['verify'] = False
        kwargs.setdefault('timeout', REQUEST_TIMEOUT)
        if self._session:
            response = self._session.request(method, url, *args, **kwargs)
        else:
            # Mimics the behaviour of requests.api.request()
            with self:
                response = self._session.request(method, url, *args, **kwargs)
        if raise_for_status:
            response.raise_for_status()
        return response

    def delete(self, endpoint, **kwargs):
        kwargs.setdefault('headers', {'Accept': 'application/json'})
        url = get_endpoint_url(self.base_url, endpoint)
        return self.send_request('DELETE', url, **kwargs)

    def get(self, endpoint, *args, **kwargs):
        kwargs.setdefault('headers', {'Accept': 'application/json'})
        kwargs.setdefault('allow_redirects', True)
        url = get_endpoint_url(self.base_url, endpoint)
        return self.send_request('GET', url, *args, **kwargs)

    def post(self, endpoint, data=None, json=None, *args, **kwargs):
        kwargs.setdefault('headers', {
            'Content-type': 'application/json',
            'Accept': 'application/json'
        })
        url = get_endpoint_url(self.base_url, endpoint)
        return self.send_request('POST', url, *args,
                                 data=data, json=json, **kwargs)

    def put(self, endpoint, data=None, json=None, *args, **kwargs):
        kwargs.setdefault('headers', {
            'Content-type': 'application/json',
            'Accept': 'application/json'
        })
        url = get_endpoint_url(self.base_url, endpoint)
        return self.send_request('PUT', url, *args,
                                 data=data, json=json, **kwargs)

    def notify_exception(self, message=None, details=None):
        self.notify_error(message, details)
        notify_exception(None, message, details)

    def notify_error(self, message, details=None):
        from corehq.motech.views import ConnectionSettingsListView

        if not self.notify_addresses:
            return
        message_lines = [
            message,
            '',
            _('Project space: {}').format(self.domain_name),
            _('Remote API base URL: {}').format(self.base_url),
        ]
        if self.payload_id:
            message_lines.append(_('Payload ID: {}').format(self.payload_id))
        if details:
            message_lines.extend(['', details])
        connection_settings_url = absolute_reverse(
            ConnectionSettingsListView.urlname, args=[self.domain_name])
        message_lines.extend([
            '',
            _('*Why am I getting this email?*'),
            _('This address is configured in CommCare HQ as a notification '
              'address for integration errors.'),
            '',
            _('*How do I unsubscribe?*'),
            _('Open Connection Settings in CommCare HQ ({}) and remove your '
              'email address from the "Addresses to send notifications" field '
              'for remote connections. If necessary, please provide an '
              'alternate address.').format(connection_settings_url),
        ])
        send_mail_async.delay(
            _('MOTECH Error'),
            '\r\n'.join(message_lines),
            recipient_list=self.notify_addresses,
            domain=self.domain_name,
            use_domain_gateway=True,
        )


def get_basic_requests(domain_name, base_url, username, password, **kwargs):
    """
    Returns a Requests instance with basic auth.
    """
    kwargs['auth_manager'] = BasicAuthManager(username, password)
    return Requests(domain_name, base_url, **kwargs)


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


def simple_request(domain, url, data, *, headers, auth_manager, verify,
                   method="POST", notify_addresses=None, payload_id=None):
    if isinstance(data, str):
        # Encode as UTF-8, otherwise requests will send data containing
        # non-ASCII characters as 'data:application/octet-stream;base64,...'
        data = data.encode('utf-8')
    default_headers = CaseInsensitiveDict({
        "content-type": "text/xml",
        "content-length": str(len(data)),
    })
    default_headers.update(headers)
    requests = Requests(
        domain,
        base_url=url,
        verify=verify,
        auth_manager=auth_manager,
        notify_addresses=notify_addresses,
        payload_id=payload_id,
    )

    request_methods = {
        REQUEST_DELETE: requests.delete,
        REQUEST_POST: requests.post,
        REQUEST_PUT: requests.put,
    }
    try:
        request_method = request_methods[method]
    except KeyError:
        raise ValueError(f"Method must be one of {', '.join(request_methods.keys())}")

    try:
        response = request_method(None, data=data, headers=default_headers)
    except Exception as err:
        requests.notify_error(str(err))
        raise
    if not 200 <= response.status_code < 300:
        message = f'HTTP status code {response.status_code}: {response.text}'
        requests.notify_error(message)
    return response


def simple_post(domain, url, data, *, headers, auth_manager, verify,
                notify_addresses=None, payload_id=None):
    """
    POST with a cleaner API, and return the actual HTTPResponse object, so
    that error codes can be interpreted.
    """
    return simple_request(
        domain,
        url,
        data,
        headers=headers,
        auth_manager=auth_manager,
        verify=verify,
        notify_addresses=notify_addresses,
        payload_id=payload_id,
        method="POST",
    )


def json_or_http_error(response):
    try:
        return response.json()
    except ValueError as err:
        raise HTTPError(
            'Invalid JSON response from remote service',
            response=response,
        ) from err


def validate_user_input_url_for_repeaters(url, domain, src):
    try:
        validate_user_input_url(url)
    except InvalidURL:
        pass
    except PossibleSSRFAttempt as e:
        if settings.DEBUG and e.reason == 'is_loopback':
            pass
        else:
            metrics_counter('commcare.security.ssrf_attempt', tags={
                'domain': domain,
                'src': src,
                'reason': e.reason
            })
            notify_exception(None, 'Possible SSRF Attempt', details={
                'domain': domain,
                'src': src,
                'reason': e.reason,
            })
            raise
