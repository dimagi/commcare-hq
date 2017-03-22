import json
import logging
import requests
from corehq.apps.dhis2.dbaccessors import get_dhis2_connection


logger = logging.getLogger('json_api_logger')


class JsonApiError(Exception):
    """
    JsonApiError is raised for HTTP or socket errors.
    """
    pass


def json_serializer(obj):
    """
    A JSON serializer that serializes dates and times
    """
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()


def log_request(func):

    def log(log_level, json_api_request, request_error, response_status, response_body, path, data=None, **params):
        """
        Unpack path and data from args and kwargs in order to log them separately
        """
        logger.log(log_level, {
            'domain': json_api_request.domain_name if json_api_request.domain_name is not None else '[N/A]',
            'request_method': func.__name__.upper(),
            'request_url': json_api_request.server_url + path,
            'request_headers': json.dumps(json_api_request.headers),
            'request_params': json.dumps(params),
            'request_body': '' if data is None else json.dumps(data, default=json_serializer),

            'request_error': request_error,
            'response_status': response_status,
            'response_body': response_body,
        })

    def request_wrapper(self, *args, **kwargs):
        domain_log_level = get_dhis2_connection(self.domain_name).get('log_level', logging.INFO)
        log_level = logging.INFO
        request_error = ''
        response_status = None
        response_body = ''
        try:
            status, response = func(self, *args, **kwargs)
            response_status = status
            response_body = '' if response is None else json.dumps(response)
        except Exception as err:
            log_level = logging.ERROR
            request_error = str(err)
            raise err
        else:
            return status, response
        finally:
            if log_level >= domain_log_level:
                log(log_level, self, request_error, response_status, response_body, *args, **kwargs)

    return request_wrapper


class JsonApiRequest(object):
    """
    Wrap requests with URL, header and authentication for DHIS2 API
    """

    def __init__(self, server_url, username, password, domain_name=None):
        self.server_url = server_url if server_url.endswith('/') else server_url + '/'
        self.headers = {'Accept': 'application/json'}
        self.auth = (username, password)
        self.domain_name = domain_name

    @staticmethod
    def json_or_error(response):
        """
        Return HTTP status, JSON

        :raises JsonApiError: if HTTP status is not in the 200 (OK) range
        """
        if 200 <= response.status_code < 300:
            return response.status_code, response.json() if response.content else None
        else:
            raise JsonApiError('API request to {} failed with HTTP status {}: {}'.format(
                response.url, response.status_code, response.text))

    @log_request
    def get(self, path, **kwargs):
        path = path.lstrip('/')
        try:
            response = requests.get(self.server_url + path, headers=self.headers, auth=self.auth, **kwargs)
        except requests.RequestException as err:
            raise JsonApiError(str(err))
        return self.json_or_error(response)

    @log_request
    def delete(self, path, **kwargs):
        path = path.lstrip('/')
        try:
            response = requests.delete(self.server_url + path, headers=self.headers, auth=self.auth, **kwargs)
        except requests.RequestException as err:
            raise JsonApiError(str(err))
        return self.json_or_error(response)

    @log_request
    def post(self, path, data, **kwargs):
        path = path.lstrip('/')
        # Make a copy of self.headers so as not to set content type on requests that don't send content
        headers = dict(self.headers, **{'Content-type': 'application/json'})
        json_data = json.dumps(data, default=json_serializer)
        try:
            response = requests.post(self.server_url + path, json_data, headers=headers, auth=self.auth, **kwargs)
        except requests.RequestException as err:
            raise JsonApiError(str(err))
        return self.json_or_error(response)

    @log_request
    def put(self, path, data, **kwargs):
        path = path.lstrip('/')
        headers = dict(self.headers, **{'Content-type': 'application/json'})
        json_data = json.dumps(data, default=json_serializer)
        try:
            response = requests.put(self.server_url + path, json_data, headers=headers, auth=self.auth, **kwargs)
        except requests.RequestException as err:
            raise JsonApiError(str(err))
        return self.json_or_error(response)
