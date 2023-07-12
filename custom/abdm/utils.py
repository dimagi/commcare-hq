import json

import requests
from django.conf import settings
from rest_framework.pagination import PageNumberPagination

from corehq.form_processor.models.cases import CommCareCase
from custom.abdm.const import SESSIONS_PATH


def check_for_existing_abha_number(domain, abha_number):
    return bool(CommCareCase.objects.get_case_by_external_id(domain=domain, external_id=abha_number))


# TODO Refactor this same code in M1 and use for all of them
class TokenException(Exception):
    pass


def get_access_token():
    if not settings.ABDM_CLIENT_ID or not settings.ABDM_CLIENT_SECRET:
        raise TokenException("Missing client credentials for ABDM. Unable to get token.")
    payload = {"clientId": settings.ABDM_CLIENT_ID, "clientSecret": settings.ABDM_CLIENT_SECRET}
    headers = {"Content-Type": "application/json; charset=UTF-8"}
    resp = requests.post(url=settings.ABDM_GATEWAY_URL + SESSIONS_PATH, data=json.dumps(payload), headers=headers)
    resp.raise_for_status()
    return resp.json().get("accessToken")


def get_response_http_post(api_url, payload, additional_headers=None):

    req_url = settings.ABDM_GATEWAY_URL + api_url
    print(f"Sending request to {req_url} with payload: {payload}")
    headers = {"Content-Type": "application/json"}
    try:
        token = get_access_token()
    except Exception as e:
        raise TokenException(f"Access token could not be fetched. Error {e}")
    headers.update({"Authorization": "Bearer {}".format(token)})
    data = json.dumps(payload)
    if additional_headers:
        headers.update(additional_headers)
    resp = requests.post(url=req_url, data=json.dumps(payload), headers=headers)
    resp.raise_for_status()
    print(f"Response received with status code: {resp.status_code}")
    if resp.status_code != 202:
        print(f"Response data: {resp.json()}")
    return {} if resp.status_code == 202 else resp.json()


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 1
    page_size_query_param = 'page'
    max_page_size = 1000
