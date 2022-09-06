from django.contrib.auth import authenticate
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.status import (HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND, HTTP_200_OK)
from rest_framework.response import Response

from custom.abdm.milestone_one.utils import abha_creation_util as abdm_util


def login(request):
    username = request.data.get("username")
    password = request.data.get("password")
    if username is None or password is None:
        return Response({'error': 'Please provide both username and password'}, status=HTTP_400_BAD_REQUEST)
    user = authenticate(username=username, password=password)
    if not user:
        return Response({'error': 'Invalid Credentials'}, status=HTTP_404_NOT_FOUND)
    token, _ = Token.objects.get_or_create(user=user)
    return token.key


@api_view(["POST"])
@permission_classes((IsAuthenticated,))
def generate_aadhaar_otp(request):
    aadhaar_number = request.data.get("aadhaar")
    resp = abdm_util.generate_aadhar_otp(aadhaar_number)
    return Response(resp, status=HTTP_200_OK)


@api_view(["POST"])
@permission_classes((IsAuthenticated,))
def generate_mobile_otp(request):
    txn_id = request.data.get("txn_id")
    mobile_number = request.data.get("mobile_number")
    resp = abdm_util.generate_mobile_otp(mobile_number, txn_id)
    return Response(resp, status=HTTP_200_OK)


@api_view(["POST"])
@permission_classes((IsAuthenticated,))
def verify_aadhaar_otp(request):
    txn_id = request.data.get("txn_id")
    otp = request.data.get("otp")
    resp = abdm_util.verify_aadhar_otp(otp, txn_id)
    return Response(resp, status=HTTP_200_OK)


@api_view(["POST"])
@permission_classes((IsAuthenticated,))
def verify_mobile_otp(request):
    txn_id = request.data.get("txn_id")
    otp = request.data.get("otp")
    resp = abdm_util.verify_mobile_otp(otp, txn_id)
    return Response(resp, status=HTTP_200_OK)
