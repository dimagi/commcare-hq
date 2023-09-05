from custom.abdm.hip.models import HIPConsentArtefact
from rest_framework.response import Response
from rest_framework.status import HTTP_202_ACCEPTED

from custom.abdm.const import (
    STATUS_EXPIRED,
    STATUS_REVOKED,
)
from custom.abdm.hip.const import (
    GW_CONSENT_REQUEST_ON_NOTIFY_PATH,
)
from custom.abdm.hip.serializers.consents import (
    GatewayConsentRequestNotifySerializer,
)
from custom.abdm.hip.views.base import HIPGatewayBaseView
from custom.abdm.utils import (
    GatewayRequestHelper,
)


class GatewayConsentRequestNotify(HIPGatewayBaseView):

    def post(self, request, format=None):
        print("GatewayConsentRequestNotify", request.data)
        GatewayConsentRequestNotifySerializer(data=request.data).is_valid(raise_exception=True)
        self.process_request(request.data)
        return Response(status=HTTP_202_ACCEPTED)

    def process_request(self, request_data):
        artefact_id = request_data['notification']['consentId']
        if request_data['notification']['status'] in (STATUS_REVOKED, STATUS_EXPIRED):
            HIPConsentArtefact.objects.get(artefact_id=artefact_id).delete()
            # self.gateway_consents_on_notify(artefact_id, request_data['requestId'])
        else:
            consent_artefact = HIPConsentArtefact(artefact_id=artefact_id,
                                                  signature=request_data['notification']['signature'],
                                                  details=request_data['notification']['consentDetail'],
                                                  grant_acknowledgement=request_data['notification']
                                                  ['grantAcknowledgement'])
            consent_artefact.save()
        self.gateway_consents_on_notify(artefact_id, request_data['requestId'])

    def gateway_consents_on_notify(self, artefact_id, request_id):
        request_data = GatewayRequestHelper.common_request_data()
        request_data['acknowledgement'] = {'status': 'OK', 'consentId': artefact_id}
        request_data['resp'] = {'requestId': request_id}
        GatewayRequestHelper().post(GW_CONSENT_REQUEST_ON_NOTIFY_PATH, request_data)
