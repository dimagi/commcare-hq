from rest_framework.views import APIView

from custom.abdm.hip.exceptions import hip_exception_handler, hip_gateway_exception_handler


class HIPBaseView(APIView):

    def get_exception_handler(self):
        return hip_exception_handler


class HIPGatewayBaseView(APIView):

    def get_exception_handler(self):
        return hip_gateway_exception_handler
