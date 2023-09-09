import json
import uuid
from datetime import datetime

import requests
from dateutil import parser
from django.conf import settings
from memoized import memoized
from rest_framework import serializers
from rest_framework.pagination import PageNumberPagination

from corehq.form_processor.models.cases import CommCareCase
from custom.abdm.const import SESSIONS_PATH
from custom.abdm.exceptions import ABDMConfigurationError, ERROR_FUTURE_DATE_MESSAGE, ERROR_PAST_DATE_MESSAGE, \
    ABDMServiceUnavailable, ABDMGatewayError


def check_for_existing_abha_number(domain, abha_number):
    return bool(CommCareCase.objects.get_case_by_external_id(domain=domain, external_id=abha_number))


class ABDMRequestHelper:
    REQUIRED_CONFIGS = ['ABDM_ABHA_URL', 'ABDM_GATEWAY_URL', 'ABDM_CLIENT_ID', 'ABDM_CLIENT_SECRET', 'ABDM_X_CM_ID']
    gateway_base_url = None
    abha_base_url = None
    token_payload = None

    @classmethod
    @memoized
    def _check_configs(cls):
        if any(not hasattr(settings, config) for config in cls.REQUIRED_CONFIGS):
            raise ABDMConfigurationError("Missing required configurations for ABDM!")
        cls.gateway_base_url = settings.ABDM_GATEWAY_URL
        cls.abha_base_url = settings.ABDM_ABHA_URL
        cls.token_payload = {"clientId": settings.ABDM_CLIENT_ID, "clientSecret": settings.ABDM_CLIENT_SECRET}

    def __init__(self):
        self._check_configs()
        self.headers = {'Content-Type': "application/json", 'X-CM-ID': settings.ABDM_X_CM_ID}

    def get_access_token(self):
        # TODO Handle token error
        headers = {"Content-Type": "application/json; charset=UTF-8"}
        resp = requests.post(url=self.gateway_base_url + SESSIONS_PATH, data=json.dumps(self.token_payload),
                             headers=headers)
        resp.raise_for_status()
        return resp.json().get("accessToken")

    def gateway_post(self, api_path, payload, additional_headers=None):
        print(f"Gateway Call: {api_path} with data : {payload}")
        url = self.gateway_base_url + api_path
        try:
            resp = self._post(url, payload, additional_headers)
        except requests.Timeout:
            raise ABDMServiceUnavailable()
        except requests.HTTPError as err:
            raise ABDMGatewayError(detail=err)
        return self.gateway_json_from_response(resp)

    def abha_post(self, api_path, payload, additional_headers=None):
        print(f"Abha Call: {api_path} with data : {payload}")
        url = self.abha_base_url + api_path
        resp = self._post(url, payload, additional_headers)
        # ABHA APIS may not return 'application/json' content type in headers as per swagger doc
        return _get_json_from_resp(resp)

    def _post(self, url, payload, additional_headers=None):
        self.headers.update({"Authorization": f"Bearer {self.get_access_token()}"})
        if additional_headers:
            self.headers.update(additional_headers)
        resp = requests.post(url=url, data=json.dumps(payload), headers=self.headers)
        print(f"Response headers {resp.headers}")
        print(f"Response status code : {resp.status_code} and JSON: {_get_json_from_resp(resp)}")
        resp.raise_for_status()
        return resp

    @staticmethod
    def gateway_json_from_response(resp):
        # All Gateway APIs returns 202 without json response for success
        # and (400, 401, 500) with json response for error
        resp_json = {}
        content_type = resp.headers.get('content-type')
        if content_type and 'application/json' in content_type:
            resp_json = _get_json_from_resp(resp)
        return resp_json

    @staticmethod
    def common_request_data():
        return {'requestId': str(uuid.uuid4()), 'timestamp': datetime.utcnow().isoformat()}


def _get_json_from_resp(resp):
    try:
        return resp.json()
    except ValueError:
        return {}


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 1
    page_size_query_param = 'page_size'
    max_page_size = 1000


def future_date_validator(value):
    if value <= datetime.utcnow():
        raise serializers.ValidationError(ERROR_FUTURE_DATE_MESSAGE)


def past_date_validator(value):
    if value > datetime.utcnow():
        raise serializers.ValidationError(ERROR_PAST_DATE_MESSAGE)


def abdm_iso_to_datetime(value):
    """Converts varying iso format datetime obtained from ABDM to python datetime"""
    return parser.isoparse(value).replace(tzinfo=None).replace(microsecond=0)


def json_from_file(file_path):
    with open(file_path) as file:
        return json.load(file)


# Configuration to set celery task (may be exposed as django setting)
# from celery import shared_task
from corehq.apps.celery.shared_task import task

task = task
ABDM_QUEUE = 'background_queue'
