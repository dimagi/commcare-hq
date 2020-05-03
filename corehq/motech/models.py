import re

from django.core.serializers.json import DjangoJSONEncoder
from django.db import models

import jsonfield

from corehq.motech.auth import api_auth_settings_choices
from corehq.motech.const import ALGO_AES, AUTH_TYPES, PASSWORD_PLACEHOLDER
from corehq.motech.utils import b64_aes_decrypt, b64_aes_encrypt


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
            ciphertext=b64_aes_encrypt(plaintext)
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
            ciphertext=b64_aes_encrypt(plaintext)
            self.client_secret = f'${ALGO_AES}${ciphertext}'

    @property
    def notify_addresses(self):
        return [addr for addr in re.split('[, ]+', self.notify_addresses_str) if addr]

    def get_requests(self, payload_id, logger):
        from corehq.motech.requests import Requests
        return Requests(
            self.domain,
            self.url,
            self.username,
            self.plaintext_password,
            verify=not self.skip_cert_verify,
            notify_addresses=self.notify_addresses,
            payload_id=payload_id,
            logger=logger,
            auth_type=self.auth_type,
        )


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
    request_body = jsonfield.JSONField(
        blank=True, null=True,  # NULL for GET, but POST can take an empty body
        dump_kwargs={'cls': DjangoJSONEncoder, 'separators': (',', ':')}  # Use DjangoJSONEncoder for dates, etc.
    )
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
            request_body=log_entry.data,
            request_error=log_entry.error,
            response_status=log_entry.response_status,
            response_body=log_entry.response_body,
        )
