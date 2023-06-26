from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import IsAuthenticated

from custom.abdm.auth import ABDMUserAuthentication
from custom.abdm.milestone_one.utils import abha_creation_util as abdm_util
from custom.abdm.milestone_one.utils.decorators import required_request_params
from custom.abdm.milestone_one.utils.response_util import parse_response
from custom.abdm.utils import check_for_existing_abha_number


@api_view(["POST"])
@permission_classes((IsAuthenticated,))
@authentication_classes((ABDMUserAuthentication,))
@required_request_params(["aadhaar"])
def generate_aadhaar_otp(request):
    aadhaar_number = request.data.get("aadhaar")
    raw_response = abdm_util.generate_aadhaar_otp(aadhaar_number)
    return parse_response(raw_response)


@api_view(["POST"])
@permission_classes((IsAuthenticated,))
@authentication_classes((ABDMUserAuthentication,))
@required_request_params(["txn_id", "mobile_number"])
def generate_mobile_otp(request):
    txn_id = request.data.get("txn_id")
    mobile_number = request.data.get("mobile_number")
    resp = abdm_util.generate_mobile_otp(mobile_number, txn_id)
    return parse_response(resp)


@api_view(["POST"])
@permission_classes((IsAuthenticated,))
@authentication_classes((ABDMUserAuthentication,))
@required_request_params(["txn_id", "otp"])
def verify_aadhaar_otp(request):
    txn_id = request.data.get("txn_id")
    otp = request.data.get("otp")
    resp = abdm_util.verify_aadhar_otp(otp, txn_id)
    return parse_response(resp)


@api_view(["POST"])
@permission_classes((IsAuthenticated,))
@authentication_classes((ABDMUserAuthentication,))
@required_request_params(["txn_id", "otp"])
def verify_mobile_otp(request):
    txn_id = request.data.get("txn_id")
    otp = request.data.get("otp")
    health_id = request.data.get("health_id")
    resp = abdm_util.verify_mobile_otp(otp, txn_id)
    if resp and "txnId" in resp:
        resp = abdm_util.create_health_id(txn_id, health_id)
        resp["user_token"] = resp.pop("token")
        resp.pop("refreshToken")
        resp["exists_on_abdm"] = not resp.pop("new")
        resp["exists_on_hq"] = check_for_existing_abha_number(request.user.domain, health_id)
    return parse_response(resp)
