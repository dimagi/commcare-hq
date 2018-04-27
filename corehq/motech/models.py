from __future__ import absolute_import
from __future__ import unicode_literals

import jsonfield
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models


class RequestLog(models.Model):
    """
    Store API requests and responses to analyse errors and keep an audit trail
    """
    domain = models.CharField(max_length=126, db_index=True)  # 126 seems to be a popular length
    timestamp = models.DateTimeField(auto_now_add=True)
    log_level = models.IntegerField(null=True)
    request_method = models.CharField(max_length=12)
    request_url = models.CharField(max_length=255)
    request_headers = jsonfield.JSONField(blank=True)
    request_params = jsonfield.JSONField(blank=True)
    request_body = jsonfield.JSONField(
        blank=True, null=True,  # NULL for GET, but POST can take an empty body
        dump_kwargs={'cls': DjangoJSONEncoder, 'separators': (',', ':')}  # Use DjangoJSONEncoder for dates, etc.
    )
    request_error = models.TextField(null=True)
    response_status = models.IntegerField(null=True)
    response_body = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'dhis2_jsonapilog'

    @staticmethod
    def log(log_level, domain_name, request_error, response_status, response_body, request_headers, method_func,
            request_url, data=None, **params):
        # The order of params is important: `method_func`, `request_url` and `data` are the requests function and
        # its args respectively. Having these params at the end allows us to call `log` with `*args, **kwargs`

        # Don't log credentials
        if 'auth' in params:
            params['auth'] = '******'
        RequestLog.objects.create(
            domain=domain_name,
            log_level=log_level,
            request_method=method_func.__name__.upper(),
            request_url=request_url,
            request_headers=request_headers,
            request_params=params,
            request_body=data,
            request_error=request_error,
            response_status=response_status,
            response_body=response_body,
        )
