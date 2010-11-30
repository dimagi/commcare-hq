from django.utils.datastructures import SortedDict


class WWWAuthenticateError(Exception):
    pass


class BaseAuth(object):
    def __init__(self, username, password):
        self.username = username
        self.password = password

    def _authenticate_headers(self, response):
        return SortedDict([(value.split(' ', 1)[0], value)
                           for header, value in response.items()
                           if header == 'WWW-Authenticate'])

    def _update_headers(self, request, response):
        auth = self.authorization(request, response)
        return auth and {'HTTP_AUTHORIZATION': auth} or {}

    def __call__(self, request, response=None):
        return self._update_headers(request, response)
