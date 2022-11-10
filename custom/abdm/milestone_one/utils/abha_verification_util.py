import requests

from custom.abdm.milestone_one.utils.request_util import get_access_token, get_response_http_post, base_url


def generate_auth_otp(health_id, auth_method):
    auth_otp_url = "v2/auth/init"
    payload = {"authMethod": auth_method, "healthid": health_id}
    return get_response_http_post(auth_otp_url, payload)


def confirm_with_mobile_otp(otp, txn_id):
    confirm_with_mobile_otp_url = "v1/auth/confirmWithMobileOTP"
    payload = {"otp": otp, "txnId": txn_id}
    return get_response_http_post(confirm_with_mobile_otp_url, payload)


def confirm_with_aadhaar_otp(otp, txn_id):
    confirm_with_aadhaar_otp_url = "v1/auth/confirmWithAadhaarOtp"
    payload = {"otp": otp, "txnId": txn_id}
    return get_response_http_post(confirm_with_aadhaar_otp_url, payload)


def get_account_information(x_token):
    account_information_url = "v1/account/profile"
    headers = {"Content-Type": "application/json; charset=UTF-8"}
    token = get_access_token()
    headers.update({"Authorization": "Bearer {}".format(token), "X-Token": f"Bearer {x_token}"})
    resp = requests.get(url=base_url + account_information_url, headers=headers)
    return resp.json()


def search_by_health_id(health_id):
    search_by_health_id_url = "v1/search/searchByHealthId"
    payload = {"healthId": health_id}
    return get_response_http_post(search_by_health_id_url, payload)
