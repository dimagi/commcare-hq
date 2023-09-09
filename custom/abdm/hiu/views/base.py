from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from custom.abdm.auth import ABDMUserAuthentication
from custom.abdm.hiu.exceptions import hiu_exception_handler, hiu_gateway_exception_handler
from custom.abdm.hiu.tasks import sample_background_task
from custom.abdm.settings import ABDM_AUTH_CLASS

class HIUBaseView(APIView):
    authentication_classes = [ABDMUserAuthentication]
    permission_classes = [IsAuthenticated]

    def get_exception_handler(self):
        return hiu_exception_handler


class HIUGatewayBaseView(APIView):
    def get_exception_handler(self):
        return hiu_gateway_exception_handler


class TestBackgroundCelery(APIView):
    authentication_classes = [ABDM_AUTH_CLASS]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        print("TestBackgroundCelery", request.data)
        sample_background_task.delay(request.data)
        return Response(status=202)
