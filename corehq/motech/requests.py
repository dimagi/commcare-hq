from __future__ import absolute_import
from __future__ import unicode_literals

import logging

from corehq.motech.utils import pformat_json


logger = logging.getLogger('motech')


class Requests(object):
    def __init__(self, domain_name, base_url, username, password):
        import requests
        self.requests = requests
        self.domain_name = domain_name
        self.base_url = base_url
        self.username = username
        self.password = password

    def send_request(self, method_func, *args, **kwargs):
        raise_for_status = kwargs.pop('raise_for_status', False)
        try:
            response = method_func(*args, **kwargs)
            if raise_for_status:
                response.raise_for_status()
        except self.requests.RequestException as err:
            err_request, err_response = parse_request_exception(err)
            logger.error('Request: %s', err_request)
            logger.error('Response: %s', err_response)
            raise
        return response

    def get_url(self, uri):
        return '/'.join((self.base_url.rstrip('/'), uri.lstrip('/')))

    def delete(self, uri, **kwargs):
        return self.requests.delete(self.get_url(uri),
                                    auth=(self.username, self.password), **kwargs)

    def get(self, uri, *args, **kwargs):
        return self.send_request(self.requests.get, self.get_url(uri), *args,
                                 auth=(self.username, self.password), **kwargs)

    def post(self, uri, *args, **kwargs):
        return self.send_request(self.requests.post, self.get_url(uri), *args,
                                 auth=(self.username, self.password), **kwargs)


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
    err_content = pformat_json(err.response.content)  # pformat_json returns non-JSON values unchanged
    err_response = '\n\n'.join((str(err), err_content))
    return err_request, err_response