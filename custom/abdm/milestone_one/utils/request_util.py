import json
from typing import Any, Dict
import requests

from django.conf import settings

base_url = "https://healthidsbx.abdm.gov.in/api/"
gateway_url = "https://dev.abdm.gov.in/gateway/v0.5/sessions"


def get_access_token():
    payload = {"clientId": settings.ABDM_CLIENT_ID, "clientSecret": settings.ABDM_CLIENT_SECRET}
    headers = {"Content-Type": "application/json; charset=UTF-8"}
    resp = requests.post(url=gateway_url, data=json.dumps(payload), headers=headers)
    if resp.status_code == 200:
        return resp.json().get("accessToken")


def get_response_http_post(api_url: str,
                           payload: Dict[str, Any],
                           additional_headers: Dict[str, str] = None) -> Dict[Any, Any]:
    req_url = base_url + api_url
    headers = {"Content-Type": "application/json"}
    token = get_access_token()
    headers.update({"Authorization": "Bearer {}".format(token)})
    if additional_headers:
        headers.update(additional_headers)
    resp = requests.post(url=req_url, data=json.dumps(payload), headers=headers)
    return resp.json()
