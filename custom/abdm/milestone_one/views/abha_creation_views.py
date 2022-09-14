from django.contrib.auth import authenticate
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.status import HTTP_404_NOT_FOUND, HTTP_200_OK
from rest_framework.response import Response

from custom.abdm.milestone_one.utils import abha_creation_util as abdm_util
from custom.abdm.milestone_one.utils.decorators import required_request_params
from custom.abdm.milestone_one.utils.response_handler import get_response


@api_view(["POST"])
@permission_classes((AllowAny,))
@required_request_params(["username", "password"])
def login(request):
    username = request.data.get("username")
    password = request.data.get("password")
    user = authenticate(username=username, password=password)
    if not user:
        return Response({'error': 'Invalid Credentials'}, status=HTTP_404_NOT_FOUND)
    token, _ = Token.objects.get_or_create(user=user)
    return Response({'token': token.key}, status=HTTP_200_OK)


@api_view(["POST"])
@permission_classes((IsAuthenticated,))
@required_request_params(["aadhaar"])
def generate_aadhaar_otp(request):
    aadhaar_number = request.data.get("aadhaar_number")
    resp = abdm_util.generate_aadhar_otp(aadhaar_number)
    return get_response(resp)


@api_view(["POST"])
@permission_classes((IsAuthenticated,))
@required_request_params(["txn_id", "mobile_number"])
def generate_mobile_otp(request):
    txn_id = request.data.get("txn_id")
    mobile_number = request.data.get("mobile_number")
    resp = abdm_util.generate_mobile_otp(mobile_number, txn_id)
    return get_response(resp)


@api_view(["POST"])
@permission_classes((IsAuthenticated,))
@required_request_params(["txn_id", "otp"])
def verify_aadhaar_otp(request):
    txn_id = request.data.get("txn_id")
    otp = request.data.get("otp")
    resp = abdm_util.verify_aadhar_otp(otp, txn_id)
    return get_response(resp)


@api_view(["POST"])
@permission_classes((IsAuthenticated,))
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
