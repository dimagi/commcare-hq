from django.contrib.auth import authenticate
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
    HTTP_200_OK
)
from rest_framework.response import Response

from custom.abdm.abdm_util import generate_aadhar_otp


def login(request):
    username = request.data.get("username")
    password = request.data.get("password")
    if username is None or password is None:
        return Response({'error': 'Please provide both username and password'},
                        status=HTTP_400_BAD_REQUEST)
    user = authenticate(username=username, password=password)
    if not user:
        return Response({'error': 'Invalid Credentials'},
                        status=HTTP_404_NOT_FOUND)
    token, _ = Token.objects.get_or_create(user=user)
    #return Response({'token': token.key}, status=HTTP_200_OK)
    return token.key


#@csrf_exempt
@api_view(["POST"])
@permission_classes((IsAuthenticated,))
def generate_aadhaar_otp(request):
    print(request.data)
    data = request.data.get("aadhaar")
    resp = generate_aadhar_otp(data)
    #data = {'sample_data': 123}
    return Response(resp, status=HTTP_200_OK)
