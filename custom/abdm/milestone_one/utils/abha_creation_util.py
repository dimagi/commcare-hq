import logging

from custom.abdm.milestone_one.utils.request_util import get_response_http_post

logger = logging.getLogger(__name__)

REG_API_URL = "v1/registration/aadhaar/"
GENERATE_AADHAAR_OTP_URL = REG_API_URL + "generateOtp"
GENERATE_MOBILE_OTP_URL = REG_API_URL + "generateMobileOTP"
VERIFY_AADHAAR_OTP_URL = REG_API_URL + "verifyOTP"
VERIFY_MOBILE_OTP_URL = REG_API_URL + "verifyMobileOTP"
CREATE_HEALTH_ID_URL = REG_API_URL + "createHealthIdWithPreVerified"


def generate_aadhar_otp(aadhaar_number):
    payload = {"aadhaar": str(aadhaar_number)}
    return get_response_http_post(GENERATE_AADHAAR_OTP_URL, payload)


def generate_mobile_otp(mobile_number, txnid):
    payload = {"mobile": str(mobile_number), "txnId": txnid}
    return get_response_http_post(GENERATE_MOBILE_OTP_URL, payload)


def verify_aadhar_otp(otp, txnid):
    payload = {"otp": str(otp), "txnId": txnid}
    return get_response_http_post(VERIFY_AADHAAR_OTP_URL, payload)


def verify_mobile_otp(otp, txnid):
    payload = {"otp": str(otp), "txnId": txnid}
    return get_response_http_post(VERIFY_MOBILE_OTP_URL, payload)


def create_health_id(txnid):
    """
    We send empty data in payload as value of these parameters are fetched by ABDM app
    through Aadhar Number from UIDAI, which user has already authenticated using OTP.
    Info about what things are already authenticated, is tracked using txnId.
    """
    payload = {
        "txnId": txnid
    }
    return get_response_http_post(CREATE_HEALTH_ID_URL, payload)
