import json
import re
from typing import Callable, Optional

from django.db import models
from django.utils.functional import cached_property
from django.utils.translation import gettext as _

import jsonfield

import corehq.motech.auth
from corehq.motech.auth import (
    AuthManager,
    BasicAuthManager,
    BearerAuthManager,
    DigestAuthManager,
    OAuth1Manager,
    OAuth2PasswordGrantManager,
    api_auth_settings_choices,
    oauth1_api_endpoints,
    oauth2_api_settings,
)
from corehq.motech.const import (
    ALGO_AES,
    AUTH_TYPES,
    BASIC_AUTH,
    BEARER_AUTH,
    DIGEST_AUTH,
    OAUTH1,
    OAUTH2_PWD,
    PASSWORD_PLACEHOLDER,
)
from corehq.motech.utils import b64_aes_decrypt, b64_aes_encrypt
from corehq.util import as_text


class ConnectionSettings(models.Model):
    """
    Stores the connection details of a remote API.

    Used for DHIS2 aggregated data / DataSet integration. Intended also
    to be used for Repeaters and OpenMRS Importers.
    """
    domain = models.CharField(max_length=126, db_index=True)
    name = models.CharField(max_length=255)
    url = models.CharField(max_length=255)
    auth_type = models.CharField(
        max_length=16, null=True, blank=True,
        choices=(
            (None, "None"),
            *AUTH_TYPES,
        )
    )
    api_auth_settings = models.CharField(
        max_length=64, null=True, blank=True,
        choices=api_auth_settings_choices,
    )
    username = models.CharField(max_length=255, null=True, blank=True)
    password = models.CharField(max_length=255, blank=True)
    # OAuth 2.0 Password Grant needs username, password, client_id & client_secret
    client_id = models.CharField(max_length=255, null=True, blank=True)
    client_secret = models.CharField(max_length=255, blank=True)
    skip_cert_verify = models.BooleanField(default=False)
    notify_addresses_str = models.CharField(max_length=255, default="")
    # last_token is stored encrypted because it can contain secrets
    last_token_aes = models.TextField(blank=True, default="")

    def __str__(self):
        return self.name

    @property
    def plaintext_password(self):
        if self.password.startswith(f'${ALGO_AES}$'):
            ciphertext = self.password.split('$', 2)[2]
            return b64_aes_decrypt(ciphertext)
        return self.password

    @plaintext_password.setter
    def plaintext_password(self, plaintext):
        if plaintext != PASSWORD_PLACEHOLDER:
            ciphertext = b64_aes_encrypt(plaintext)
            self.password = f'${ALGO_AES}${ciphertext}'

    @property
    def plaintext_client_secret(self):
        if self.client_secret.startswith(f'${ALGO_AES}$'):
            ciphertext = self.client_secret.split('$', 2)[2]
            return b64_aes_decrypt(ciphertext)
        return self.client_secret

    @plaintext_client_secret.setter
    def plaintext_client_secret(self, plaintext):
        if plaintext != PASSWORD_PLACEHOLDER:
            ciphertext = b64_aes_encrypt(plaintext)
            self.client_secret = f'${ALGO_AES}${ciphertext}'

    @property
    def last_token(self) -> Optional[dict]:
        if self.last_token_aes:
            plaintext = b64_aes_decrypt(self.last_token_aes)
            return json.loads(plaintext)
        return None

    @last_token.setter
    def last_token(self, token: Optional[dict]):
        if token is None:
            self.last_token_aes = ''
        else:
            plaintext = json.dumps(token)
            self.last_token_aes = b64_aes_encrypt(plaintext)

    @property
    def notify_addresses(self):
        return [addr for addr in re.split('[, ]+', self.notify_addresses_str) if addr]

    def get_requests(
        self,
        payload_id: Optional[str] = None,
        logger: Optional[Callable] = None,
    ):
        from corehq.motech.requests import Requests

        auth_manager = self.get_auth_manager()
        return Requests(
            self.domain,
            self.url,
            verify=not self.skip_cert_verify,
            auth_manager=auth_manager,
            notify_addresses=self.notify_addresses,
            payload_id=payload_id,
            logger=logger,
        )

    def get_auth_manager(self):
        if self.auth_type is None:
            return AuthManager()
        if self.auth_type == BASIC_AUTH:
            return BasicAuthManager(
                self.username,
                self.plaintext_password,
            )
        if self.auth_type == DIGEST_AUTH:
            return DigestAuthManager(
                self.username,
                self.plaintext_password,
            )
        if self.auth_type == OAUTH1:
            return OAuth1Manager(
                client_id=self.client_id,
                client_secret=self.plaintext_client_secret,
                api_endpoints=self._get_oauth1_api_endpoints(),
                connection_settings=self,
            )
        if self.auth_type == BEARER_AUTH:
            return BearerAuthManager(
                self.username,
                self.plaintext_password,
            )
        if self.auth_type == OAUTH2_PWD:
            return OAuth2PasswordGrantManager(
                self.url,
                self.username,
                self.plaintext_password,
                client_id=self.client_id,
                client_secret=self.plaintext_client_secret,
                api_settings=self._get_oauth2_api_settings(),
                connection_settings=self,
            )

    def _get_oauth1_api_endpoints(self):
        if self.api_auth_settings in dict(oauth1_api_endpoints):
            return getattr(corehq.motech.auth, self.api_auth_settings)
        raise ValueError(_(
            f'Unable to resolve API endpoints {self.api_auth_settings!r}. '
            'Please select the applicable API auth settings for the '
            f'{self.name!r} connection.'
        ))

    def _get_oauth2_api_settings(self):
        if self.api_auth_settings in dict(oauth2_api_settings):
            return getattr(corehq.motech.auth, self.api_auth_settings)
        raise ValueError(_(
            f'Unable to resolve API settings {self.api_auth_settings!r}. '
            'Please select the applicable API auth settings for the '
            f'{self.name!r} connection.'
        ))

    @cached_property
    def used_by(self):
        """
        Returns the names of kinds of things that are currently using
        this instance. Used for informing users, and determining whether
        the instance can be deleted.
        """
        from corehq.motech.repeaters.models import Repeater

        kinds = set()
        if self.incrementalexport_set.exists():
            kinds.add(_('Incremental Exports'))
        if self.sqldatasetmap_set.exists():
            kinds.add(_('DHIS2 DataSet Maps'))
        if any(r.connection_settings_id == self.id
                for r in Repeater.by_domain(self.domain)):
            kinds.add(_('Data Forwarding'))

        # TODO: Check OpenmrsImporters (when OpenmrsImporters use ConnectionSettings)

        return kinds


class RequestLog(models.Model):
    """
    Store API requests and responses to analyse errors and keep an audit trail
    """
    domain = models.CharField(max_length=126, db_index=True)  # 126 seems to be a popular length
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    log_level = models.IntegerField(null=True)
    # payload_id is set for requests that are caused by a payload (e.g.
    # a form submission -- in which case payload_id will have the value
    # of XFormInstanceSQL.form_id). It also uniquely identifies a Repeat
    # Record, so it can be used to link a Repeat Record with the
    # requests to send its payload.
    payload_id = models.CharField(max_length=126, blank=True, null=True, db_index=True)
    request_method = models.CharField(max_length=12)
    request_url = models.CharField(max_length=255, db_index=True)
    request_headers = jsonfield.JSONField(blank=True)
    request_params = jsonfield.JSONField(blank=True)
    request_body = models.TextField(blank=True, null=True)
    request_error = models.TextField(null=True)
    response_status = models.IntegerField(null=True, db_index=True)
    response_body = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'dhis2_jsonapilog'

    @staticmethod
    def log(level, log_entry):
        return RequestLog.objects.create(
            domain=log_entry.domain,
            log_level=level,
            payload_id=log_entry.payload_id,
            request_method=log_entry.method,
            request_url=log_entry.url,
            request_headers=log_entry.headers,
            request_params=log_entry.params,
            request_body=as_text(log_entry.data),
            request_error=log_entry.error,
            response_status=log_entry.response_status,
            response_body=as_text(log_entry.response_body),
        )
