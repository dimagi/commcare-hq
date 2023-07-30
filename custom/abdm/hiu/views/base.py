from rest_framework.views import APIView

from custom.abdm.hiu.exceptions import hiu_exception_handler, hiu_gateway_exception_handler


class HIUBaseView(APIView):

    def get_exception_handler(self):
        return hiu_exception_handler


class HIUGatewayBaseView(APIView):

    def get_exception_handler(self):
        return hiu_gateway_exception_handler
