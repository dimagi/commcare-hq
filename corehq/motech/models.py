import json
import re
from typing import Any, Callable, Optional

from django.db import models
from django.utils.functional import cached_property
from django.utils.translation import gettext as _

import attr
import jsonfield

import corehq.motech.auth
from corehq.motech.auth import (
    AuthManager,
    BasicAuthManager,
    BearerAuthManager,
    DigestAuthManager,
    OAuth1Manager,
    OAuth2ClientGrantManager,
    OAuth2PasswordGrantManager,
    api_auth_settings_choices,
    oauth1_api_endpoints,
    ApiKeyAuthManager,
)
from corehq.motech.const import (
    ALGO_AES,
    AUTH_TYPES,
    BASIC_AUTH,
    BEARER_AUTH,
    DIGEST_AUTH,
    MAX_REQUEST_LOG_LENGTH,
    OAUTH1,
    OAUTH2_CLIENT,
    OAUTH2_PWD,
    PASSWORD_PLACEHOLDER, APIKEY_AUTH,
)
from corehq.motech.utils import b64_aes_decrypt, b64_aes_encrypt
from corehq.util import as_json_text, as_text


@attr.s(auto_attribs=True, frozen=True, kw_only=True)
class RequestLogEntry:
    domain: str
    payload_id: str
    method: str
    url: str
    headers: dict
    params: dict
    data: Any
    error: str
    response_status: int
    response_headers: dict
    response_body: str


class ConnectionQuerySet(models.QuerySet):

    def delete(self):
        from .repeaters.models import Repeater
        repeaters = Repeater.all_objects.filter(connection_settings_id__in=list(self.values_list("id", flat=True)))
        if repeaters.exists():
            raise models.ProtectedError(
                "Cannot delete ConnectionSettings with related Repeater(s)",
                repeaters,
            )
        return super().delete()


class ConnectionSoftDeleteManager(models.Manager):

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


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
    token_url = models.CharField(max_length=255, blank=True, null=True)
    refresh_url = models.CharField(max_length=255, blank=True, null=True)
    pass_credentials_in_header = models.BooleanField(default=None, null=True)
    notify_addresses_str = models.CharField(max_length=255, default="")
    # last_token is stored encrypted because it can contain secrets
    last_token_aes = models.TextField(blank=True, default="")
    is_deleted = models.BooleanField(default=False, db_index=True)

    objects = ConnectionSoftDeleteManager.from_queryset(ConnectionQuerySet)()
    all_objects = ConnectionQuerySet.as_manager()

    def __str__(self):
        return self.name

    @property
    def repeaters(self):
        from .repeaters.models import Repeater
        return Repeater.objects.filter(connection_settings_id=self.id)

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
        # Auth types that don't require a username:
        if self.auth_type is None:
            return AuthManager()
        if self.auth_type == OAUTH1:
            return OAuth1Manager(
                client_id=self.client_id,
                client_secret=self.plaintext_client_secret,
                api_endpoints=self._get_oauth1_api_endpoints(),
                connection_settings=self,
            )
        if self.auth_type == OAUTH2_CLIENT:
            return OAuth2ClientGrantManager(
                self.url,
                client_id=self.client_id,
                client_secret=self.plaintext_client_secret,
                token_url=self.token_url,
                refresh_url=self.refresh_url,
                pass_credentials_in_header=self.pass_credentials_in_header,
                connection_settings=self,
            )

        # Auth types that require a username:
        if not isinstance(self.username, str):
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
        if self.auth_type == BEARER_AUTH:
            return BearerAuthManager(
                self.username,
                self.plaintext_password,
            )
        if self.auth_type == APIKEY_AUTH:
            return ApiKeyAuthManager(self.plaintext_password)
        if self.auth_type == OAUTH2_PWD:
            return OAuth2PasswordGrantManager(
                self.url,
                self.username,
                self.plaintext_password,
                client_id=self.client_id,
                client_secret=self.plaintext_client_secret,
                token_url=self.token_url,
                refresh_url=self.refresh_url,
                pass_credentials_in_header=self.pass_credentials_in_header,
                connection_settings=self,
            )
        raise ValueError(f'Unknown auth type {self.auth_type!r}')

    def _get_oauth1_api_endpoints(self):
        if self.api_auth_settings in dict(oauth1_api_endpoints):
            return getattr(corehq.motech.auth, self.api_auth_settings)
        raise ValueError(_(
            f'Unable to resolve API endpoints {self.api_auth_settings!r}. '
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

        kinds = set()
        if self.sqldatasetmap_set.exists():
            kinds.add(_('DHIS2 DataSet Maps'))
        if self.repeaters.exists():
            kinds.add(_('Data Forwarding'))

        # TODO: Check OpenmrsImporters (when OpenmrsImporters use ConnectionSettings)

        return kinds

    def delete(self):
        if self.repeaters.exists():
            raise models.ProtectedError(
                "Cannot delete ConnectionSettings with related Repeater(s)",
                self.repeaters,
            )
        return super().delete()

    def soft_delete(self):
        self.is_deleted = True
        self.save()


class RequestLog(models.Model):
    """
    Store API requests and responses to analyse errors and keep an audit trail
    """
    domain = models.CharField(max_length=126, db_index=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    log_level = models.IntegerField(null=True)
    # payload_id is set for requests that are caused by a payload (e.g.
    # a form submission -- in which case payload_id will have the value
    # of XFormInstance.form_id). It also uniquely identifies a Repeat
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
    response_headers = jsonfield.JSONField(blank=True, null=True)
    response_body = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'dhis2_jsonapilog'

    @staticmethod
    def log(level: int, log_entry: RequestLogEntry):
        return RequestLog.objects.create(
            domain=log_entry.domain,
            log_level=level,
            payload_id=log_entry.payload_id,
            request_method=log_entry.method,
            request_url=log_entry.url,
            request_headers=log_entry.headers,
            request_params=log_entry.params,
            request_body=as_json_text(log_entry.data)[:MAX_REQUEST_LOG_LENGTH],
            request_error=log_entry.error,
            response_status=log_entry.response_status,
            response_headers=log_entry.response_headers,
            response_body=as_text(log_entry.response_body)[:MAX_REQUEST_LOG_LENGTH],
        )
