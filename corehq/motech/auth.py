from datetime import datetime

import jsonobject
from requests.auth import HTTPBasicAuth, AuthBase, HTTPDigestAuth

from corehq.motech.const import BASIC_AUTH, DIGEST_AUTH, BEARER_AUTH


def get_auth_factory(connection_settings):
    return {
        BASIC_AUTH: BasicAuthFactory,
        DIGEST_AUTH: DigestAuthFactory,
        BEARER_AUTH: BearerAuthFactory
    }[connection_settings.auth_type](connection_settings)


class BearerProps(jsonobject.JsonObject):
    token = jsonobject.StringProperty()
    expiry = jsonobject.DateTimeProperty()
    refresh_token = jsonobject.StringProperty()

    @property
    def is_valid(self):
        return self.token and self.expiry and self.expiry > datetime.utcnow()


class AuthFactory(AuthBase):
    def __init__(self, connection_settings):
        self.connection_settings = connection_settings
        self._auth = None
        self._prepare()

    def _prepare(self):
        pass

    def __call__(self, r):
        return self._auth(r)


class BasicAuthFactory(AuthFactory):
    def _prepare(self):
        self._auth = HTTPBasicAuth(self.connection_settings.username, self.connection_settings.plaintext_password)


class DigestAuthFactory(AuthFactory):
    def _prepare(self):
        self._auth = HTTPDigestAuth(self.connection_settings.username, self.connection_settings.plaintext_password)


class BearerAuthFactory(AuthFactory):
    def _prepare(self):
        props = self.connection_settings.properties
        self._props = BearerProps.wrap(props) if props else BearerProps()

    def __call__(self, r):
        if not self._props.is_valid:
            self._init_token()
        r.headers["Authorization"] = f"Bearer {self._props.token}"
        return r

    def _init_token(self):
        if self._props.refresh_token:
            self._refresh_token()
        else:
            self._get_token()

    def _refresh_token(self):
        # do request to refresh token
        # self._props = ....
        self._save()

    def _get_token(self):
        # do request to get new token
        # self._props = ....
        self._save()

    def _save(self):
        self.connection_settings.properties = self._props.to_json()
        self.connection_settings.save()
