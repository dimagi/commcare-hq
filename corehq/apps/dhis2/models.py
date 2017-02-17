import json
import logging
import requests

from dimagi.ext.couchdbkit import Document, StringProperty


class Dhis2Connection(Document):
    domain = StringProperty()
    server_url = StringProperty()
    username = StringProperty()
    password = StringProperty()


class JsonApiError(Exception):
    """
    JsonApiError is raised for HTTP or socket errors.
    """
    pass


class Dhis2ApiQueryError(JsonApiError):
    """
    Dhis2ApiQueryError is raised when the API returns an unexpected response.
    """
    pass


class Dhis2ConfigurationError(Exception):
    """
    DHIS2 API Integration has not been configured correctly.
    """
    pass


class Dhis2IntegrationError(Exception):
    """
    A failure has occurred in CommCareHQ related to but not caused by DHIS2.
    """
    pass


def json_serializer(obj):
    """
    A JSON serializer that serializes dates and times
    """
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()


class JsonApiRequest(object):
    """
    Wrap requests with URL, header and authentication for DHIS2 API
    """

    def __init__(self, host, username, password):
        self.baseurl = host + '/api/'
        self.headers = {'Accept': 'application/json'}
        self.auth = (username, password)

    @staticmethod
    def json_or_error(response):
        """
        Return HTTP status, JSON

        :raises JsonApiError: if HTTP status is not in the 200 (OK) range
        """
        if 200 <= response.status_code < 300:
            return response.json()
        else:
            raise JsonApiError('API request to {} failed with HTTP status {}: {}'.format(
                response.url, response.status_code, response.text))

    def get(self, path, **kwargs):
        logging.debug(
            'DHIS2: GET %s: \n'
            '    Headers: %s\n'
            '    kwargs: %s',
            self.baseurl + path, self.headers, kwargs
        )
        try:
            response = requests.get(self.baseurl + path, headers=self.headers, auth=self.auth, **kwargs)
        except requests.RequestException as err:
            logging.exception(
                'JSON API raised HTTP or socket error.\n'
                'Request details: %s\n'
                'Error: %s',
                {'method': 'get', 'url': self.baseurl + path, 'headers': self.headers},
                err)
            raise JsonApiError(str(err))
        return JsonApiRequest.json_or_error(response)

    def post(self, path, data, **kwargs):
        # Make a copy of self.headers because setting content type on requests that don't send content is bad
        headers = self.headers.copy()
        headers['Content-type'] = 'application/json'
        json_data = json.dumps(data, default=json_serializer)
        logging.debug(
            'DHIS2: POST %s: \n'
            '    Headers: %s\n'
            '    Data: %s\n'
            '    kwargs: %s',
            self.baseurl + path, self.headers, json_data, kwargs
        )
        try:
            response = requests.post(self.baseurl + path, json_data, headers=headers, auth=self.auth, **kwargs)
        except requests.RequestException as err:
            logging.exception(
                'JSON API raised HTTP or socket error.\n'
                'Request details: %s\n'
                'Error: %s',
                {'method': 'post', 'url': self.baseurl + path, 'data': json_data, 'headers': headers},
                err
            )
            raise JsonApiError(str(err))
        return JsonApiRequest.json_or_error(response)

    def put(self, path, data, **kwargs):
        headers = self.headers.copy()
        headers['Content-type'] = 'application/json'
        json_data = json.dumps(data, default=json_serializer)
        logging.debug(
            'DHIS2: PUT %s: \n'
            '    Headers: %s\n'
            '    Data: %s\n'
            '    kwargs: %s',
            self.baseurl + path, self.headers, json_data, kwargs
        )
        try:
            response = requests.put(self.baseurl + path, json_data, headers=headers, auth=self.auth, **kwargs)
        except requests.RequestException as err:
            logging.exception(
                'JSON API raised HTTP or socket error.\n'
                'Request details: %s\n'
                'Error: %s',
                {'method': 'put', 'url': self.baseurl + path, 'data': json_data, 'headers': headers},
                err
            )
            raise JsonApiError(str(err))
        return JsonApiRequest.json_or_error(response)
