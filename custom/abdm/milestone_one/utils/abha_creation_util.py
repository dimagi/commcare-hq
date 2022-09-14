import requests
import json
import logging

from django.conf import settings

base_url = "https://healthidsbx.abdm.gov.in/api/"
gateway_url = "https://dev.abdm.gov.in/gateway/v0.5/sessions"
logger = logging.getLogger(__name__)


def get_access_token():
    payload = {"clientId": settings.ABDM_CLIENT_ID, "clientSecret": settings.ABDM_CLIENT_SECRET}
    headers = {"Content-Type": "application/json; charset=UTF-8"}
    resp = requests.post(url=gateway_url, data=json.dumps(payload), headers=headers)
    if resp.status_code == 200:
        logger.info("Received token info from abdm")
        return resp.json().get("accessToken")


def generate_aadhar_otp(aadhaar_number):
    generate_aadhar_otp = "v1/registration/aadhaar/generateOtp"
    data = {"aadhaar": str(aadhaar_number)}
    headers = {"Content-Type": "application/json"}
    token = get_access_token()
    logging.info(f"Received access token {token}")
    headers.update({"Authorization": "Bearer {}".format(token)})
    url = base_url + generate_aadhar_otp
    print(f"url {url}")
    print(data)
    print(headers)
    resp = requests.post(url=url, data=data, headers=headers)
    print(resp.content)
    return resp.json()


def generate_mobile_otp(mobile_number, txnid):
    generate_aadhar_otp = "v1/registration/aadhaar/generateMobileOTP"
    payload = {"mobile": str(mobile_number), "txnId": txnid}
    headers = {"Content-Type": "application/json; charset=UTF-8"}
    token = get_access_token()
    headers.update({"Authorization": "Bearer {}".format(token)})
    resp = requests.post(url=base_url + generate_aadhar_otp, data=json.dumps(payload), headers=headers)
    return resp.json()


def verify_aadhar_otp(otp, txnid):
    generate_aadhar_otp = "v1/registration/aadhaar/verifyOTP"
    payload = {"otp": str(otp), "txnId": txnid}
    headers = {"Content-Type": "application/json; charset=UTF-8"}
    token = get_access_token()
    headers.update({"Authorization": "Bearer {}".format(token)})
    resp = requests.post(url=base_url + generate_aadhar_otp, data=json.dumps(payload), headers=headers)
    return resp.json()


def verify_mobile_otp(otp, txnid):
    generate_aadhar_otp = "v1/registration/aadhaar/verifyMobileOTP"
    payload = {"otp": str(otp), "txnId": txnid}
    headers = {"Content-Type": "application/json; charset=UTF-8"}
    token = get_access_token()
    headers.update({"Authorization": "Bearer {}".format(token)})
    resp = requests.post(url=base_url + generate_aadhar_otp, data=json.dumps(payload), headers=headers)
    return resp.json()


def create_health_id(txnid):
    generate_aadhar_otp = "v1/registration/aadhaar/createHealthIdWithPreVerified"
    payload = {
        "email": "",
        "firstName": "",
        "healthId": "",
        "lastName": "",
        "middleName": "",
        "password": "",
        "profilePhoto": "",
        "txnId": txnid
    }
    headers = {"Content-Type": "application/json; charset=UTF-8"}
    token = get_access_token()
    headers.update({"Authorization": "Bearer {}".format(token)})
    resp = requests.post(url=base_url + generate_aadhar_otp, data=json.dumps(payload), headers=headers)
    return resp.json()
