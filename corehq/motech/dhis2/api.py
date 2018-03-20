from __future__ import absolute_import
from __future__ import unicode_literals
import json
import logging
import requests
from django.core.serializers.json import DjangoJSONEncoder
from corehq.motech.dhis2.dbaccessors import get_dhis2_connection
from corehq.motech.dhis2.models import JsonApiLog


class JsonApiError(Exception):
    """
    JsonApiError is raised for HTTP or socket errors.
    """
    pass


def log_request(func):

    def request_wrapper(self, *args, **kwargs):
        dhis2_conn = get_dhis2_connection(self.domain_name)
        domain_log_level = getattr(dhis2_conn, 'log_level', logging.INFO)
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
            raise err
        else:
            return response
        finally:
            if log_level >= domain_log_level:
                JsonApiLog.log(log_level, self, request_error, response_status, response_body, *args, **kwargs)

    return request_wrapper


class JsonApiRequest(object):
    """
    Wrap requests with URL, header and authentication for DHIS2 API
    """

    def __init__(self, domain_name, server_url, username, password):
        self.domain_name = domain_name
        self.server_url = server_url if server_url.endswith('/') else server_url + '/'
        self.headers = {'Accept': 'application/json'}
        self.auth = (username, password)

    @staticmethod
    def json_or_error(response):
        """
        Return HTTP status, JSON

        :raises JsonApiError: if HTTP status is not in the 200 (OK) range
        """
        if not 200 <= response.status_code < 300:
            raise JsonApiError('API request to {} failed with HTTP status {}: {}'.format(
                response.url, response.status_code, response.text))
        if response.content:
            try:
                response.json()
            except ValueError:
                raise JsonApiError('API response is not valid JSON: {}'.format(response.content))
        return response

    def get_request_url(self, path):
        return self.server_url + path.lstrip('/')

    @log_request
    def send_request(self, method_func, *args, **kwargs):
        try:
            response = method_func(*args, **kwargs)
        except requests.RequestException as err:
            raise JsonApiError(str(err))
        return self.json_or_error(response)

    def get(self, path, **kwargs):
        return self.send_request(
            requests.get, self.get_request_url(path), headers=self.headers, auth=self.auth, **kwargs
        )

    def delete(self, path, **kwargs):
        return self.send_request(
            requests.delete, self.get_request_url(path), headers=self.headers, auth=self.auth, **kwargs
        )

    def post(self, path, data, **kwargs):
        # Make a copy of self.headers so as not to set content type on requests that don't send content
        headers = dict(self.headers, **{'Content-type': 'application/json'})
        json_data = json.dumps(data, cls=DjangoJSONEncoder)
        return self.send_request(
            requests.post, self.get_request_url(path), json_data, headers=headers, auth=self.auth, **kwargs
        )

    def put(self, path, data, **kwargs):
        headers = dict(self.headers, **{'Content-type': 'application/json'})
        json_data = json.dumps(data, cls=DjangoJSONEncoder)
        return self.send_request(
            requests.put, self.get_request_url(path), json_data, headers=headers, auth=self.auth, **kwargs
        )
