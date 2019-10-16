import logging

from django.conf import settings

import requests

from dimagi.utils.logging import notify_exception

from corehq.apps.hqwebapp.tasks import send_mail_async
from corehq.motech.const import REQUEST_TIMEOUT
from corehq.motech.models import RequestLog
from corehq.motech.utils import pformat_json

logger = logging.getLogger('motech')


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
            RequestLog.log(log_level, self.domain_name, request_error, response_status, response_body,
                           *args, **kwargs)

    return request_wrapper


class Requests(object):
    """
    Wraps the requests library to simplify use with JSON REST APIs.

    Sets auth headers automatically, and requests JSON responses by
    default.

    To maintain a session of authenticated non-API requests, use
    Requests as a context manager.
    """

    def __init__(self, domain_name, base_url, username, password,
                 verify=True, notify_addresses=None):
        """
        Initialise instance

        :param domain_name: Domain to store logs under
        :param base_url: Remote API base URL
        :param username: Remote API username
        :param password: Remote API plaintext password
        :param verify: Verify SSL certificate?
        :param notify_addresses: A list of email addresses to notify of
            errors.
        """
        self.domain_name = domain_name
        self.base_url = base_url
        self.username = username
        self.password = password
        self.verify = verify
        self.notify_addresses = [] if notify_addresses is None else notify_addresses
        self._session = None

    def __enter__(self):
        self._session = requests.Session()
        return self

    def __exit__(self, *args):
        self._session.close()
        self._session = None

    @log_request
    def send_request(self, method, *args, **kwargs):
        raise_for_status = kwargs.pop('raise_for_status', False)
        if not self.verify:
            kwargs['verify'] = False
        kwargs.setdefault('timeout', REQUEST_TIMEOUT)
        try:
            if self._session:
                response = self._session.request(method, *args, **kwargs)
            else:
                # Mimics the behaviour of requests.api.request()
                with requests.Session() as session:
                    response = session.request(method, *args, **kwargs)
            if raise_for_status:
                response.raise_for_status()
        except requests.RequestException:
            # commented out since these are spamming Sentry
            # err_request, err_response = parse_request_exception(err)
            # logger.error('Request: %s', err_request)
            # logger.error('Response: %s', err_response)
            raise
        return response

    def get_url(self, uri):
        return '/'.join((self.base_url.rstrip('/'), uri.lstrip('/')))

    def delete(self, uri, **kwargs):
        kwargs.setdefault('headers', {'Accept': 'application/json'})
        return self.send_request('DELETE', self.get_url(uri),
                                 auth=(self.username, self.password), **kwargs)

    def get(self, uri, *args, **kwargs):
        kwargs.setdefault('headers', {'Accept': 'application/json'})
        kwargs.setdefault('allow_redirects', True)
        return self.send_request('GET', self.get_url(uri), *args,
                                 auth=(self.username, self.password), **kwargs)

    def post(self, uri, data=None, json=None, *args, **kwargs):
        kwargs.setdefault('headers', {
            'Content-type': 'application/json',
            'Accept': 'application/json'
        })
        return self.send_request('POST', self.get_url(uri), *args,
                                 data=data, json=json,
                                 auth=(self.username, self.password), **kwargs)

    def notify_exception(self, message=None, details=None):
        self.notify_error(message, details)
        notify_exception(None, message, details)

    def notify_error(self, message, details=None):
        if not self.notify_addresses:
            return
        message_body = '\r\n'.join((
            message,
            f'Project space: {self.domain_name}',
            f'Remote API base URL: {self.base_url}',
            f'Remote API username: {self.username}',
        ))
        if details:
            message_body += f'\r\n\r\n{details}'
        send_mail_async.delay(
            'MOTECH Error',
            message_body,
            from_email=settings.DEFAULT_FROM_ADDRESS,
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
