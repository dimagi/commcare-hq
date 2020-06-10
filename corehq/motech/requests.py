import logging
from functools import wraps
from typing import Callable, Optional

from django.conf import settings

import attr
from requests.structures import CaseInsensitiveDict

from dimagi.utils.logging import notify_exception

from corehq.apps.hqwebapp.tasks import send_mail_async
from corehq.motech.auth import AuthManager, BasicAuthManager
from corehq.motech.const import REQUEST_TIMEOUT
from corehq.motech.models import RequestLog
from corehq.motech.utils import (
    get_endpoint_url,
    pformat_json,
    unpack_request_args,
)


@attr.s(frozen=True)
class RequestLogEntry:
    domain = attr.ib()
    payload_id = attr.ib()
    method = attr.ib()
    url = attr.ib()
    headers = attr.ib()
    params = attr.ib()
    data = attr.ib()
    error = attr.ib()
    response_status = attr.ib()
    response_body = attr.ib()


def log_request(self, func, logger):

    @wraps(func)
    def request_wrapper(method, url, *args, **kwargs):
        log_level = logging.INFO
        request_error = ''
        response_status = None
        response_body = ''
        try:
            response = func(method, url, *args, **kwargs)
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
            params, data, headers = unpack_request_args(method, args, kwargs)
            entry = RequestLogEntry(
                self.domain_name, self.payload_id, method, url, headers, params, data,
                request_error, response_status, response_body
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
        self.send_request = log_request(self, self._send_request, self.logger)
        self._session = None

    def __enter__(self):
        self._session = self.auth_manager.get_session()
        return self

    def __exit__(self, *args):
        self._session.close()
        self._session = None

    def _send_request(self, method, *args, **kwargs):
        raise_for_status = kwargs.pop('raise_for_status', False)
        if not self.verify:
            kwargs['verify'] = False
        kwargs.setdefault('timeout', REQUEST_TIMEOUT)
        if self._session:
            response = self._session.request(method, *args, **kwargs)
        else:
            # Mimics the behaviour of requests.api.request()
            with self.auth_manager.get_session() as session:
                response = session.request(method, *args, **kwargs)
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
        if not self.notify_addresses:
            return
        message_lines = [
            message,
            f'Project space: {self.domain_name}',
            f'Remote API base URL: {self.base_url}',
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


def simple_post(domain, url, data, *, headers, auth_manager, verify,
                notify_addresses=None, payload_id=None):
    """
    POST with a cleaner API, and return the actual HTTPResponse object, so
    that error codes can be interpreted.
    """
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
        base_url=None,
        verify=verify,
        auth_manager=auth_manager,
        notify_addresses=notify_addresses,
        payload_id=payload_id,
    )
    return requests.post(url, data=data, headers=default_headers)
