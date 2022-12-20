import requests

from custom.abdm.milestone_one.utils.request_util import (
    base_url,
    get_access_token,
    get_response_http_post,
)

auth_otp_url = "v2/auth/init"
confirm_with_mobile_otp_url = "v1/auth/confirmWithMobileOTP"
confirm_with_aadhaar_otp_url = "v1/auth/confirmWithAadhaarOtp"
account_information_url = "v1/account/profile"
search_by_health_id_url = "v1/search/searchByHealthId"


def generate_auth_otp(health_id, auth_method):
    payload = {"authMethod": auth_method, "healthid": health_id}
    return get_response_http_post(auth_otp_url, payload)


def confirm_with_mobile_otp(otp, txn_id):
    payload = {"otp": otp, "txnId": txn_id}
    return get_response_http_post(confirm_with_mobile_otp_url, payload)


def confirm_with_aadhaar_otp(otp, txn_id):
    payload = {"otp": otp, "txnId": txn_id}
    return get_response_http_post(confirm_with_aadhaar_otp_url, payload)


def get_account_information(x_token):
    headers = {"Content-Type": "application/json; charset=UTF-8"}
    token = get_access_token()
    headers.update({"Authorization": "Bearer {}".format(token), "X-Token": f"Bearer {x_token}"})
    resp = requests.get(url=base_url + account_information_url, headers=headers)
    return resp.json()


def search_by_health_id(health_id):
    payload = {"healthId": health_id}
    return get_response_http_post(search_by_health_id_url, payload)
