import re

from django.core.serializers.json import DjangoJSONEncoder
from django.db import models

import jsonfield

from corehq.motech.const import ALGO_AES, PASSWORD_PLACEHOLDER
from corehq.motech.repeaters.models import BASIC_AUTH, DIGEST_AUTH, OAUTH1
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
        max_length=7, null=True, blank=True,
        choices=(
            (None, "None"),
            (BASIC_AUTH, "Basic"),
            (DIGEST_AUTH, "Digest"),
            (OAUTH1, "OAuth1"),
        )
    )
    username = models.CharField(max_length=255)
    password = models.CharField(max_length=255)
    skip_cert_verify = models.BooleanField(default=False)
    notify_addresses_str = models.CharField(max_length=255, default="")

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
