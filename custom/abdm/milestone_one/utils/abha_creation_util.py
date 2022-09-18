import requests
import json
import logging

from custom.abdm.milestone_one.utils.request_util import get_response_http_post

logger = logging.getLogger(__name__)


def generate_aadhar_otp(aadhaar_number):
    generate_aadhar_otp_url = "v1/registration/aadhaar/generateOtp"
    payload = {"aadhaar": str(aadhaar_number)}
    return get_response_http_post(generate_aadhar_otp_url, payload)


def generate_mobile_otp(mobile_number, txnid):
    generate_mobile_otp_url = "v1/registration/aadhaar/generateMobileOTP"
    payload = {"mobile": str(mobile_number), "txnId": txnid}
    return get_response_http_post(generate_mobile_otp_url, payload)


def verify_aadhar_otp(otp, txnid):
    verify_aadhaar_otp_url = "v1/registration/aadhaar/verifyOTP"
    payload = {"otp": str(otp), "txnId": txnid}
    return get_response_http_post(verify_aadhaar_otp_url, payload)


def verify_mobile_otp(otp, txnid):
    verify_mobile_otp_url = "v1/registration/aadhaar/verifyMobileOTP"
    payload = {"otp": str(otp), "txnId": txnid}
    return get_response_http_post(verify_mobile_otp_url, payload)


def create_health_id(txnid):
    create_health_id_url = "v1/registration/aadhaar/createHealthIdWithPreVerified"
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
    return get_response_http_post(create_health_id_url, payload)
