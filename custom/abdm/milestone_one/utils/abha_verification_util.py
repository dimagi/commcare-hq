import requests
import base64

from django.conf import settings


from custom.abdm.milestone_one.utils.request_util import (
    get_access_token,
    get_response_http_post,
)

AUTH_OTP_URL = "v1/auth/init"
CONFIRM_WITH_MOBILE_OTP_URL = "v1/auth/confirmWithMobileOTP"
CONFIRM_WITH_AADHAAR_OTP_URL = "v1/auth/confirmWithAadhaarOtp"
ACCOUNT_INFORMATION_URL = "v1/account/profile"
SEARCH_BY_HEALTH_ID_URL = "v1/search/searchByHealthId"
HEALTH_CARD_PNG_FORMAT = "v2/account/getPngCard"
EXISTS_BY_HEALTH_ID = "v1/search/existsByHealthId"


def generate_auth_otp(health_id, auth_method):
    payload = {"authMethod": auth_method, "healthid": health_id}
    return get_response_http_post(AUTH_OTP_URL, payload)


def confirm_with_mobile_otp(otp, txn_id):
    payload = {"otp": otp, "txnId": txn_id}
    return get_response_http_post(CONFIRM_WITH_MOBILE_OTP_URL, payload)


def confirm_with_aadhaar_otp(otp, txn_id):
    payload = {"otp": otp, "txnId": txn_id}
    return get_response_http_post(CONFIRM_WITH_AADHAAR_OTP_URL, payload)


def get_account_information(x_token):
    headers = {"Content-Type": "application/json; charset=UTF-8"}
    token = get_access_token()
    headers.update({"Authorization": "Bearer {}".format(token), "X-Token": f"Bearer {x_token}"})
    resp = requests.get(url=settings.ABDM_ABHA_URL + ACCOUNT_INFORMATION_URL, headers=headers)
    return resp.json()


def search_by_health_id(health_id):
    payload = {"healthId": health_id}
    return get_response_http_post(SEARCH_BY_HEALTH_ID_URL, payload)


def get_health_card_png(user_token):
    headers = {"Content-Type": "application/json; charset=UTF-8"}
    token = get_access_token()
    headers.update({"Authorization": "Bearer {}".format(token), "X-Token": f"Bearer {user_token}"})
    resp = requests.get(url=settings.ABDM_ABHA_URL + HEALTH_CARD_PNG_FORMAT, headers=headers, stream=True)
    if resp.status_code == 200:
        return {"health_card": base64.b64encode(resp.content)}
    return {"error": "Image could not be downloaded"}


def exists_by_health_id(health_id):
    payload = {"healthId": health_id}
    return get_response_http_post(EXISTS_BY_HEALTH_ID, payload)
