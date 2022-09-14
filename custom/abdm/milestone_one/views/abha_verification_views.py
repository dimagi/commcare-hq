from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from custom.abdm.auth import UserAuthentication

from custom.abdm.milestone_one.utils import abha_verification_util as abdm_util
from custom.abdm.milestone_one.utils.decorators import required_request_params
from custom.abdm.milestone_one.utils.response_handler import get_response


@api_view(["GET"])
@permission_classes((IsAuthenticated,))
@authentication_classes((UserAuthentication,))
@required_request_params(["health_id"])
def get_auth_methods(request):
    aadhaar_number = request.data.get("health_id")
    resp = abdm_util.search_by_health_id(aadhaar_number)
    auth_methods = resp.get("authMethods")
    resp = {"auth_methods": auth_methods}
    return get_response(resp)


@api_view(["POST"])
@permission_classes((IsAuthenticated,))
@authentication_classes((UserAuthentication,))
@required_request_params(["health_id", "auth_method"])
def generate_auth_otp(request):
    health_id = request.data.get("health_id")
    auth_method = request.data.get("auth_method")
    resp = abdm_util.generate_auth_otp(health_id, auth_method)
    return get_response(resp)


@api_view(["POST"])
@permission_classes((IsAuthenticated,))
@authentication_classes((UserAuthentication,))
@required_request_params(["txn_id", "otp"])
def confirm_with_mobile_otp(request):
    txn_id = request.data.get("txn_id")
    otp = request.data.get("otp")
    resp = abdm_util.confirm_with_mobile_otp(otp, txn_id)
    return get_response(resp)


@api_view(["POST"])
@permission_classes((IsAuthenticated,))
@authentication_classes((UserAuthentication,))
@required_request_params(["txn_id", "otp"])
def confirm_with_aadhaar_otp(request):
    txn_id = request.data.get("txn_id")
    otp = request.data.get("otp")
    resp = abdm_util.confirm_with_aadhaar_otp(otp, txn_id)
    return get_response(resp)


@api_view(["POST"])
@permission_classes((IsAuthenticated,))
@authentication_classes((UserAuthentication,))
@required_request_params(["health_id"])
def search_health_id(request):
    health_id = request.data.get("health_id")
    resp = abdm_util.search_by_health_id(health_id)
    return get_response(resp)
