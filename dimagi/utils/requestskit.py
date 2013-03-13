import urlparse
from couchdbkit import CouchdbResource
from restkit import Client
import requests
from simplejson import JSONDecodeError


def get_auth(url):
    u = urlparse.urlsplit(url)
    return (u.username, u.password) if u.username else None


class WrappedResponse(requests.Response):
    """
    Emulate restkit.wrappers.Response's API
    as well as `json_body` from couchdbkit.resource.CouchDBResponse
    """

    @property
    def status(self):
        return '%s %s' % (self.status_code, self.reason)

    @property
    def status_int(self):
        return self.status_code

    def body_string(self, charset=None, unicode_errors="strict"):
        body = self.text
        # code below copied verbatim from restkit.wrappers
        if charset is not None:
            try:
                body = body.decode(charset, unicode_errors)
            except UnicodeDecodeError:
                pass
        return body

    @property
    def json_body(self):
        try:
            return self.json()
        except JSONDecodeError:
            return self.text

    @property
    def final_url(self):
        return self.url

    def __getitem__(self, key):
        try:
            return getattr(self, key)
        except AttributeError:
            pass
        return self.headers.get(key)


class RequestsClient(Client):

    def request(self, url, method='GET', body=None, headers=None):
        print method, url
        auth = get_auth(url)
        resp = requests.request(method, url, data=body, headers=headers,
                                auth=auth)
        resp.__class__ = WrappedResponse
        return resp


class RequestsResource(CouchdbResource):

    def __init__(self, uri="http://127.0.0.1:5984", **client_opts):
        super(RequestsResource, self).__init__(uri=uri, **client_opts)
        self.client = RequestsClient()
