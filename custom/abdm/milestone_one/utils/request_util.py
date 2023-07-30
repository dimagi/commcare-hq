import json

import requests
from django.conf import settings

from custom.abdm.const import SESSIONS_PATH


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
    req_url = settings.ABDM_ABHA_URL + api_url
    headers = {"Content-Type": "application/json"}
    try:
        token = get_access_token()
    except Exception as e:
        raise TokenException(f"Access token could not be fetched. Error {e}")
    headers.update({"Authorization": "Bearer {}".format(token)})
    if additional_headers:
        headers.update(additional_headers)
    resp = requests.post(url=req_url, data=json.dumps(payload), headers=headers)
    resp.raise_for_status()
    return resp.json()
