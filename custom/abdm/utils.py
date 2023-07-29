import json
import uuid
from datetime import datetime

import requests
from django.conf import settings
from rest_framework import serializers
from rest_framework.pagination import PageNumberPagination

from corehq.form_processor.models.cases import CommCareCase
from custom.abdm.const import SESSIONS_PATH
from custom.abdm.exceptions import ABDMConfigurationException


# TODO (MI Refactor) - Any communication with HQ to be moved to integrations logic
def check_for_existing_abha_number(domain, abha_number):
    return bool(CommCareCase.objects.get_case_by_external_id(domain=domain, external_id=abha_number))


# TODO (MI Refactor) Possible if reuse the below class in M1 APIs
class GatewayRequestHelper:
    required_configs = ['ABDM_GATEWAY_URL', 'ABDM_CLIENT_ID', 'ABDM_CLIENT_SECRET', 'X_CM_ID']

    @classmethod
    def _check_configs(cls):
        print("checking")
        if any(not hasattr(settings, config) for config in cls.required_configs):
            raise ABDMConfigurationException("Missing required configurations for ABDM!")

    def __init__(self):
        self._check_configs()
        self.base_url = settings.ABDM_GATEWAY_URL
        self.token_payload = {"clientId": settings.ABDM_CLIENT_ID, "clientSecret": settings.ABDM_CLIENT_SECRET}
        self.base_headers = {'Content-Type': "application/json", 'X-CM-ID': settings.X_CM_ID}

    def get_access_token(self):
        headers = {"Content-Type": "application/json; charset=UTF-8"}
        resp = requests.post(url=self.base_url + SESSIONS_PATH, data=json.dumps(self.token_payload),
                             headers=headers)
        resp.raise_for_status()
        return resp.json().get("accessToken")

    def post(self, api_path, payload, additional_headers=None):
        token = self.get_access_token()
        req_url = self.base_url + api_path
        print(f"Sending request to {req_url} with payload: {payload}")
        headers = self.base_headers
        headers.update({"Authorization": "Bearer {}".format(token)})
        if additional_headers:
            headers.update(additional_headers)
        resp = requests.post(url=req_url, data=json.dumps(payload), headers=headers)
        print("Headers Content Type", resp.headers.get('content-type'))
        resp.raise_for_status()
        print(f"Response received with status code: {resp.status_code}")
        if resp.status_code != 202:
            print(f"Response data: {resp.json()}")
        # TODO Received 200 from gateway once instead of 202 for Fetch (Probably an error from Gateway side)
        # NOTE: For M1, we receive json data for 200, No json data for 201 and 4xx and 5xx client errors
        # NOTE: For M2/M3, we receive 202 without json data and Errors(4xx, 4xx) with json data (will be raised)
        # return {} if resp.status_code == 202 else resp.json()
        return self.handle_gateway_response(resp)

    @staticmethod
    def handle_gateway_response(resp):
        resp_json = {}
        if 'application/json' in resp.headers.get('content-type'):
            try:
                resp_json = resp.json()
            except ValueError:
                resp_json = {}
        return resp_json

    @staticmethod
    def common_request_data():
        return {'requestId': str(uuid.uuid4()), 'timestamp': datetime.utcnow().isoformat()}


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 2
    page_size_query_param = 'page'
    max_page_size = 1000


def validate_for_future_date(value):
    if value <= datetime.utcnow():
        raise serializers.ValidationError('This field must be in future')


def validate_for_past_date(value):
    if value > datetime.utcnow():
        raise serializers.ValidationError('This field must be in past')
