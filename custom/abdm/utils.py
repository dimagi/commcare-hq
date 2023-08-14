import json
import uuid
from datetime import datetime

import requests
from django.conf import settings
from rest_framework import serializers
from rest_framework.pagination import PageNumberPagination

from corehq.form_processor.models.cases import CommCareCase
from custom.abdm.const import SESSIONS_PATH
from custom.abdm.exceptions import ABDMConfigurationError, ERROR_FUTURE_DATE_MESSAGE, ERROR_PAST_DATE_MESSAGE
from memoized import memoized


def check_for_existing_abha_number(domain, abha_number):
    return bool(CommCareCase.objects.get_case_by_external_id(domain=domain, external_id=abha_number))


class GatewayRequestHelper:
    required_configs = ['ABDM_GATEWAY_URL', 'ABDM_CLIENT_ID', 'ABDM_CLIENT_SECRET', 'ABDM_X_CM_ID']
    base_url = None
    token_payload = None

    @classmethod
    @memoized
    def _check_configs(cls):
        if any(not hasattr(settings, config) for config in cls.required_configs):
            raise ABDMConfigurationError("Missing required configurations for ABDM!")
        cls.base_url = settings.ABDM_GATEWAY_URL
        cls.token_payload = {"clientId": settings.ABDM_CLIENT_ID, "clientSecret": settings.ABDM_CLIENT_SECRET}

    def __init__(self):
        self._check_configs()
        self.headers = {'Content-Type': "application/json", 'X-CM-ID': settings.ABDM_X_CM_ID}

    def get_access_token(self):
        headers = {"Content-Type": "application/json; charset=UTF-8"}
        resp = requests.post(url=self.base_url + SESSIONS_PATH, data=json.dumps(self.token_payload),
                             headers=headers)
        resp.raise_for_status()
        return resp.json().get("accessToken")

    def post(self, api_path, payload, additional_headers=None):
        self.headers.update({"Authorization": f"Bearer {self.get_access_token()}"})
        if additional_headers:
            self.headers.update(additional_headers)
        resp = requests.post(url=self.base_url + api_path, data=json.dumps(payload), headers=self.headers)
        resp.raise_for_status()
        return self.json_from_response(resp)

    @staticmethod
    def json_from_response(resp):
        resp_json = {}
        content_type = resp.headers.get('content-type')
        if content_type and 'application/json' in content_type:
            try:
                resp_json = resp.json()
            except ValueError:
                resp_json = {}
        return resp_json

    @staticmethod
    def common_request_data():
        return {'requestId': str(uuid.uuid4()), 'timestamp': datetime.utcnow().isoformat()}


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page'
    max_page_size = 1000


def future_date_validator(value):
    if value <= datetime.utcnow():
        raise serializers.ValidationError(ERROR_FUTURE_DATE_MESSAGE)


def past_date_validator(value):
    if value > datetime.utcnow():
        raise serializers.ValidationError(ERROR_PAST_DATE_MESSAGE)
