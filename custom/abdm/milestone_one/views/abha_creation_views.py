from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from custom.abdm.auth import ABDMUserAuthentication

from custom.abdm.milestone_one.utils import abha_creation_util as abdm_util
from custom.abdm.milestone_one.utils.decorators import required_request_params
from custom.abdm.milestone_one.utils.response_handler import get_response


@api_view(["POST"])
@permission_classes((IsAuthenticated,))
@authentication_classes((ABDMUserAuthentication,))
@required_request_params(["aadhaar"])
def generate_aadhaar_otp(request):
    aadhaar_number = request.data.get("aadhaar")
    resp = abdm_util.generate_aadhar_otp(aadhaar_number)
    return get_response(resp)


@api_view(["POST"])
@permission_classes((IsAuthenticated,))
@authentication_classes((ABDMUserAuthentication,))
@required_request_params(["txn_id", "mobile_number"])
def generate_mobile_otp(request):
    txn_id = request.data.get("txn_id")
    mobile_number = request.data.get("mobile_number")
    resp = abdm_util.generate_mobile_otp(mobile_number, txn_id)
    return get_response(resp)


@api_view(["POST"])
@permission_classes((IsAuthenticated,))
@authentication_classes((ABDMUserAuthentication,))
@required_request_params(["txn_id", "otp"])
def verify_aadhaar_otp(request):
    txn_id = request.data.get("txn_id")
    otp = request.data.get("otp")
    resp = abdm_util.verify_aadhar_otp(otp, txn_id)
    return get_response(resp)


@api_view(["POST"])
@permission_classes((IsAuthenticated,))
@authentication_classes((ABDMUserAuthentication,))
@required_request_params(["txn_id", "otp"])
def verify_mobile_otp(request):
    txn_id = request.data.get("txn_id")
    otp = request.data.get("otp")
    resp = abdm_util.verify_mobile_otp(otp, txn_id)
    if resp and "txnId" in resp:
        resp = abdm_util.create_health_id(txn_id)
        resp.pop("token")
        resp.pop("refreshToken")
    return get_response(resp)
