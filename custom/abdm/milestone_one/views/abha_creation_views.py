from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.status import HTTP_404_NOT_FOUND, HTTP_200_OK
from rest_framework.response import Response
from custom.abdm.auth import UserAuthentication

from custom.abdm.milestone_one.utils import abha_creation_util as abdm_util
from custom.abdm.milestone_one.utils.decorators import required_request_params
from custom.abdm.milestone_one.utils.response_handler import get_response
from custom.abdm.milestone_one.utils.user_util import get_abdm_api_token


@api_view(["POST"])
@permission_classes((AllowAny,))
@required_request_params(["username", "password"])
def login(request):
    username = request.data.get("username")
    password = request.data.get("password")
    token = get_abdm_api_token(username)
    if not token:
        return Response({'error': 'Invalid Credentials'}, status=HTTP_404_NOT_FOUND)
    return Response({'token': token}, status=HTTP_200_OK)


@api_view(["POST"])
@permission_classes((IsAuthenticated,))
@authentication_classes((UserAuthentication,))
@required_request_params(["aadhaar"])
def generate_aadhaar_otp(request):
    aadhaar_number = request.data.get("aadhaar_number")
    resp = abdm_util.generate_aadhar_otp(aadhaar_number)
    return get_response(resp)


@api_view(["POST"])
@permission_classes((IsAuthenticated,))
@authentication_classes((UserAuthentication,))
@required_request_params(["txn_id", "mobile_number"])
def generate_mobile_otp(request):
    txn_id = request.data.get("txn_id")
    mobile_number = request.data.get("mobile_number")
    resp = abdm_util.generate_mobile_otp(mobile_number, txn_id)
    return get_response(resp)


@api_view(["POST"])
@permission_classes((IsAuthenticated,))
@authentication_classes((UserAuthentication,))
@required_request_params(["txn_id", "otp"])
def verify_aadhaar_otp(request):
    txn_id = request.data.get("txn_id")
    otp = request.data.get("otp")
    resp = abdm_util.verify_aadhar_otp(otp, txn_id)
    return get_response(resp)


@api_view(["POST"])
@permission_classes((IsAuthenticated,))
@authentication_classes((UserAuthentication,))
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
