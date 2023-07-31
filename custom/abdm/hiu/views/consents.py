import requests
from custom.abdm.hiu.serializers.consents import (
    HIUGenerateConsentSerializer,
    HIUConsentRequestSerializer,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import HTTP_201_CREATED

from custom.abdm.auth import ABDMUserAuthentication
from custom.abdm.exceptions import ABDMGatewayError, ABDMServiceUnavailable
from custom.abdm.hiu.const import (
    GW_CONSENT_REQUEST_INIT_PATH,
)
from custom.abdm.hiu.exceptions import send_custom_error_response
from custom.abdm.hiu.models import HIUConsentRequest
from custom.abdm.hiu.views.base import HIUBaseView
from custom.abdm.milestone_one.utils.abha_verification_util import (
    exists_by_health_id,
)
from custom.abdm.utils import (
    GatewayRequestHelper,
)


class GenerateConsent(HIUBaseView):
    authentication_classes = [ABDMUserAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, format=None):
        print("GenerateConsent: ", request.data)
        serializer = HIUGenerateConsentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        consent_data = serializer.data
        if self.check_if_health_id_exists(consent_data["patient"]["id"]) is False:
            return send_custom_error_response(error_code=4407, details_field='patient.id')
        gateway_request_id = self.gateway_consent_request_init(consent_data)
        consent_request = self.save_consent_request(gateway_request_id, consent_data, request.user)
        return Response(status=HTTP_201_CREATED,
                        data=HIUConsentRequestSerializer(consent_request).data)

    def check_if_health_id_exists(self, health_id):
        try:
            # TODO (M1 Change) - Move this to common utils
            response = exists_by_health_id(health_id)
            return response.get('status')
        except requests.Timeout:
            raise ABDMServiceUnavailable()
        except requests.HTTPError as err:
            raise ABDMGatewayError(detail=err)

    def gateway_consent_request_init(self, consent_data):
        request_data = GatewayRequestHelper.common_request_data()
        request_data['consent'] = consent_data
        try:
            GatewayRequestHelper().post(GW_CONSENT_REQUEST_INIT_PATH, request_data)
        except requests.Timeout:
            raise ABDMServiceUnavailable()
        except requests.HTTPError as err:
            raise ABDMGatewayError(detail=err)
        return request_data["requestId"]

    def save_consent_request(self, gateway_request_id, consent_data, user):
        consent_request = HIUConsentRequest(user=user, gateway_request_id=gateway_request_id, details=consent_data)
        consent_request.update_user_amendable_details(consent_data['permission'], consent_data['hiTypes'])
        return consent_request
