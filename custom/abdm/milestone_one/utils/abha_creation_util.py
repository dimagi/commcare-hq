from custom.abdm.milestone_one.utils.request_util import get_response_http_post


REG_API_URL = "v1/registration/aadhaar/"
GENERATE_AADHAAR_OTP_URL = REG_API_URL + "generateOtp"
GENERATE_MOBILE_OTP_URL = REG_API_URL + "generateMobileOTP"
VERIFY_AADHAAR_OTP_URL = REG_API_URL + "verifyOTP"
VERIFY_MOBILE_OTP_URL = REG_API_URL + "verifyMobileOTP"
CREATE_HEALTH_ID_URL = REG_API_URL + "createHealthIdWithPreVerified"


def generate_aadhaar_otp(aadhaar_number):
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


def create_health_id(txnid, health_id=None):
    """
    Created ABHA Health ID of the user.
    Info about what things are already authenticated in the ABHA creation
    flow is tracked using txnId.
    Demographic information of user such as name, address, age, etc. are
    fetched from the Aadhaar server by ABDM and used internally in Health ID creation.
    """
    payload = {
        "txnId": txnid
    }
    if health_id:
        payload.update({"healthId": health_id})
    return get_response_http_post(CREATE_HEALTH_ID_URL, payload)
