import re

from django.contrib.postgres.fields import JSONField
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models

import jsonfield

from corehq.motech.const import (
    ALGO_AES,
    AUTH_TYPES,
    OAUTH1,
    OAUTH2_BEARER,
    PASSWORD_PLACEHOLDER,
)
from corehq.motech.utils import b64_aes_decrypt, b64_aes_encrypt


class ApiAuthSettings(models.Model):
    """
    Stores OAuth1 and OAuth 2.0 endpoints and settings for known APIs.
    Once an API is added, its settings are available to all domains.
    """
    name = models.CharField(max_length=255)  # e.g. "DHIS2"
    auth_type = models.CharField(
        max_length=7,
        choices=(
            (OAUTH1, "OAuth1"),
            (OAUTH2_BEARER, "OAuth 2.0 Bearer Tokens"),
        )
    )
    # OAuth1
    # URL for token to identify HQ. e.g. '/oauth/request_token' (Twitter)
    request_token_url = models.CharField(max_length=255, null=True, blank=True)
    # URL for user to authorize HQ. e.g. '/oauth/authorize'
    authorization_url = models.CharField(max_length=255, null=True, blank=True)
    # URL to fetch access token. e.g. '/oauth/access_token'
    access_token_url = models.CharField(max_length=255, null=True, blank=True)

    # OAuth 2.0
    # URL to fetch bearer token. e.g. '/uaa/oauth/token' (DHIS2)
    token_url = models.CharField(max_length=255, null=True, blank=True)
    # URL to refresh bearer token. e.g. '/uaa/oauth/token'
    refresh_url = models.CharField(max_length=255, null=True, blank=True)
    # Pass credentials in Basic Auth header when requesting a token?
    # Otherwise they are passed in the request body.
    pass_credentials_in_header = models.BooleanField(default=False)

    def __str__(self):
        auth_types = dict(AUTH_TYPES)
        return f"{self.name} ({auth_types[self.auth_type]})"


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
        max_length=7, null=True, blank=True,
        choices=((None, "None"),) + AUTH_TYPES
    )
    username = models.CharField(max_length=255, blank=True)
    password = models.CharField(max_length=255, blank=True)
    api_auth_settings = models.ForeignKey(
        ApiAuthSettings, null=True, on_delete=models.PROTECT
    )
    client_id = models.CharField(max_length=255, null=True, blank=True)
    client_secret = models.CharField(max_length=255, null=True, blank=True)
    skip_cert_verify = models.BooleanField(default=False)
    notify_addresses_str = models.CharField(max_length=255, default="")

    last_token = JSONField(null=True, blank=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._requests = None

    def __str__(self):
        return self.name

    @property
    def plaintext_password(self):
        if self.password.startswith('${algo}$'.format(algo=ALGO_AES)):
            ciphertext = self.password.split('$', 2)[2]
            return b64_aes_decrypt(ciphertext)
        return self.password

    @plaintext_password.setter
    def plaintext_password(self, plaintext):
        if plaintext != PASSWORD_PLACEHOLDER:
            self.password = '${algo}${ciphertext}'.format(
                algo=ALGO_AES,
                ciphertext=b64_aes_encrypt(plaintext)
            )

    @property
    def notify_addresses(self):
        return [addr for addr in re.split('[, ]+', self.notify_addresses_str) if addr]

    def get_requests(self):
        from corehq.motech.requests import Requests

        if not self._requests:
            self._requests = Requests(
                self.domain,
                self.url,
                self.username,
                self.password,
                verify=not self.skip_cert_verify,
                auth_type=self.auth_type,
                api_auth_settings=self.api_auth_settings,
                client_id=self.client_id,
                client_secret=self.client_secret,
                last_token=self.last_token or None,
                notify_addresses=self.notify_addresses,
            )
        return self._requests

    def update_last_token(self):
        if (
            self.auth_type in (OAUTH1, OAUTH2_BEARER)
            and self._requests
            and self.last_token != self._requests.last_token
        ):
            self.last_token = self._requests.last_token
            self.save()


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
    def unpack_request_args(request_method, args, kwargs):
        params = kwargs.pop('params', None)
        json_data = kwargs.pop('json', None)  # dict
        data = kwargs.pop('data', None)  # string
        if data is None:
            data = json_data
        # Don't bother trying to cast `data` as a dict.
        # RequestLog.request_body will store it, and it will be rendered
        # as prettified JSON if possible, regardless of whether it's a
        # dict or a string.
        if args:
            if request_method == 'GET':
                params = args[0]
            elif request_method == 'PUT':
                data = args[0]
        headers = kwargs.pop('headers', {})
        return params, data, headers

    @staticmethod
    def log(
        log_level,
        domain_name,
        payload_id,
        request_error,
        response_status,
        response_body,
        request_method,
        request_url,
        *args,
        **kwargs,
    ):
        # The order of arguments is important: `request_method`,
        # `request_url` and `*args` are the positional arguments of
        # `Requests.send_request()`. Having these at the end of this
        # method's args allows us to call `log` with `*args, **kwargs`
        params, data, headers = RequestLog.unpack_request_args(request_method, args, kwargs)
        RequestLog.objects.create(
            domain=domain_name,
            log_level=log_level,
            payload_id=payload_id,
            request_method=request_method,
            request_url=request_url,
            request_headers=headers,
            request_params=params,
            request_body=data,
            request_error=request_error,
            response_status=response_status,
            response_body=response_body,
        )
