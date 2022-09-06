from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.status import HTTP_200_OK
from rest_framework.response import Response

from custom.abdm.milestone_one.utils import abha_verification_util as abdm_util


@api_view(["POST"])
@permission_classes((IsAuthenticated,))
def get_auth_methods(request):
    aadhaar_number = request.data.get("aadhaar")
    resp = abdm_util.generate_aadhar_otp(aadhaar_number)
    return Response(resp, status=HTTP_200_OK)


@api_view(["POST"])
@permission_classes((IsAuthenticated,))
def generate_auth_otp(request):
    txn_id = request.data.get("txn_id")
    mobile_number = request.data.get("mobile_number")
    resp = abdm_util.generate_auth_otp(mobile_number, txn_id)
    return Response(resp, status=HTTP_200_OK)


@api_view(["POST"])
@permission_classes((IsAuthenticated,))
def confirm_with_mobile_otp(request):
    txn_id = request.data.get("txn_id")
    otp = request.data.get("otp")
    resp = abdm_util.confirm_with_mobile_otp(otp, txn_id)
    return Response(resp, status=HTTP_200_OK)


@api_view(["POST"])
@permission_classes((IsAuthenticated,))
def confirm_with_aadhaar_otp(request):
    # TODO
    txn_id = request.data.get("txn_id")
    otp = request.data.get("otp")
    resp = abdm_util.verify_mobile_otp(otp, txn_id)
    return Response(resp, status=HTTP_200_OK)
