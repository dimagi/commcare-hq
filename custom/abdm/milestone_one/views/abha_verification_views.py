from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.status import HTTP_200_OK
from rest_framework.response import Response

from custom.abdm.milestone_one.utils import abha_verification_util as abdm_util


@api_view(["GET"])
@permission_classes((IsAuthenticated,))
def get_auth_methods(request):
    aadhaar_number = request.data.get("health_id")
    resp = abdm_util.search_by_health_id(aadhaar_number)
    auth_methods = resp.get("authMethods")
    resp = {"auth_methods": auth_methods}
    return Response(resp, status=HTTP_200_OK)


@api_view(["POST"])
@permission_classes((IsAuthenticated,))
def generate_auth_otp(request):
    health_id = request.data.get("health_id")
    auth_method = request.data.get("auth_method")
    resp = abdm_util.generate_auth_otp(health_id, auth_method)
    return Response(resp, status=HTTP_200_OK)


@api_view(["POST"])
@permission_classes((IsAuthenticated,))
def confirm_with_mobile_otp(request):
    txn_id = request.data.get("txn_id")
    otp = request.data.get("otp")
    resp = abdm_util.confirm_with_mobile_otp(otp, txn_id)
    if resp and "txnId" in resp:
        resp = {"status": "success"}
    else:
        resp = {"status": "failure"}
    return Response(resp, status=HTTP_200_OK)


@api_view(["POST"])
@permission_classes((IsAuthenticated,))
def confirm_with_aadhaar_otp(request):
    txn_id = request.data.get("txn_id")
    otp = request.data.get("otp")
    resp = abdm_util.confirm_with_aadhaar_otp(otp, txn_id)
    if resp and "txnId" in resp:
        resp = {"status": "success"}
    else:
        resp = {"status": "failure"}
    return Response(resp, status=HTTP_200_OK)


@api_view(["POST"])
@permission_classes((IsAuthenticated,))
def search_health_id(request):
    health_id = request.data.get("health_id")
    resp = abdm_util.search_by_health_id(health_id)
    return Response(resp, status=HTTP_200_OK)
