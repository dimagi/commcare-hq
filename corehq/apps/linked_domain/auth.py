from __future__ import absolute_import
from __future__ import unicode_literals
from requests.auth import AuthBase


class ApiKeyAuth(AuthBase):
    def __init__(self, username, apikey):
        self.username = username
        self.apikey = apikey

    def _key(self):
        return (self.username, self.apikey)

    def __eq__(self, other):
        return self._key() == other.key()

    def __hash__(self):
        return hash(self._key())

    def __ne__(self, other):
        return not self == other

    def __call__(self, r):
        r.headers['Authorization'] = 'apikey %s:%s' % (self.username, self.apikey)
        return r
