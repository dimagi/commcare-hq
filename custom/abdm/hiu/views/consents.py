import requests
from django.db import transaction
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import HTTP_201_CREATED, HTTP_202_ACCEPTED

from custom.abdm.auth import ABDMUserAuthentication
from custom.abdm.const import (
    STATUS_ERROR,
    STATUS_EXPIRED,
    STATUS_GRANTED,
    STATUS_REQUESTED,
    STATUS_REVOKED,
)
from custom.abdm.exceptions import ABDMGatewayError, ABDMServiceUnavailable
from custom.abdm.hiu.const import (
    GW_CONSENT_REQUEST_INIT_PATH,
    GW_CONSENT_REQUEST_ON_NOTIFY_PATH,
    GW_CONSENTS_FETCH_PATH,
)
from custom.abdm.hiu.exceptions import send_custom_error_response
from custom.abdm.hiu.models import HIUConsentArtefact, HIUConsentRequest
from custom.abdm.hiu.serializers.consents import (
    GatewayConsentRequestNotifySerializer,
    GatewayConsentRequestOnFetchSerializer,
    GatewayConsentRequestOnInitSerializer,
    HIUGenerateConsentSerializer,
    HIUConsentRequestSerializer,
)
from custom.abdm.hiu.views.base import HIUBaseView, HIUGatewayBaseView
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


class GatewayConsentRequestOnInit(HIUGatewayBaseView):

    def post(self, request, format=None):
        GatewayConsentRequestOnInitSerializer(data=request.data).is_valid(raise_exception=True)
        self.process_request(request.data)
        return Response(status=HTTP_202_ACCEPTED)

    def process_request(self, request_data):
        consent_request = HIUConsentRequest.objects.get(gateway_request_id=request_data['resp']['requestId'])
        if request_data.get('consentRequest'):
            consent_request.consent_request_id = request_data['consentRequest']['id']
            consent_request.status = STATUS_REQUESTED
        elif request_data.get('error'):
            consent_request.status = STATUS_ERROR
            consent_request.error = request_data['error']
        consent_request.save()


class GatewayConsentRequestNotify(HIUGatewayBaseView):

    def post(self, request, format=None):
        GatewayConsentRequestNotifySerializer(data=request.data).is_valid(raise_exception=True)
        self.process_request(request.data)
        return Response(status=HTTP_202_ACCEPTED)

    def process_request(self, request_data):
        consent_status = request_data['notification']['status']
        consent_request_id = request_data['notification'].get('consentRequestId')
        if consent_status == STATUS_REVOKED:
            self.handle_revoked(request_data)
        else:
            consent_request = HIUConsentRequest.objects.get(consent_request_id=consent_request_id)
            consent_request.update_status(consent_status)
            if consent_status == STATUS_GRANTED:
                self.handle_granted(request_data, consent_request)
            elif consent_status == STATUS_EXPIRED:
                self.handle_expired(request_data, consent_request)

    def handle_granted(self, request_data, consent_request):
        for artefact in request_data['notification']['consentArtefacts']:
            hiu_consent_artefact = HIUConsentArtefact(artefact_id=artefact['id'], consent_request=consent_request,
                                                      status=STATUS_GRANTED)
            hiu_consent_artefact.save()
            gateway_request_id = self.gateway_fetch_artefact_details(artefact['id'])
            hiu_consent_artefact.gateway_request_id = gateway_request_id
            hiu_consent_artefact.save()

    def handle_expired(self, request_data, consent_request):
        artefact_ids = []
        for artefact in consent_request.artefacts.all():
            artefact.update_status(STATUS_EXPIRED)
            artefact_ids.append(artefact.artefact_id)
        self.gateway_consents_on_notify(artefact_ids, request_data['requestId'])

    def handle_revoked(self, request_data):
        artefact_ids = [artefact['id'] for artefact in request_data['notification']['consentArtefacts']]
        for artefact_id in artefact_ids:
            artefact = HIUConsentArtefact.objects.get(artefact_id=artefact_id)
            artefact.update_status(STATUS_REVOKED)
        if artefact_ids:
            consent_request = artefact.consent_request
            if not any(artefact.status != STATUS_REVOKED for artefact in consent_request.artefacts.all()):
                consent_request.update_status(STATUS_REVOKED)
        self.gateway_consents_on_notify(artefact_ids, request_data['requestId'])

    def gateway_fetch_artefact_details(self, artefact_id):
        request_data = GatewayRequestHelper.common_request_data()
        request_data["consentId"] = artefact_id
        GatewayRequestHelper().post(GW_CONSENTS_FETCH_PATH, request_data)
        return request_data["requestId"]

    def gateway_consents_on_notify(self, artefact_ids, request_id):
        request_data = GatewayRequestHelper.common_request_data()
        request_data['acknowledgement'] = [{'status': 'OK', 'consentId': artefact_id}
                                           for artefact_id in artefact_ids]
        request_data['resp'] = {'requestId': request_id}
        GatewayRequestHelper().post(GW_CONSENT_REQUEST_ON_NOTIFY_PATH, request_data)


class GatewayConsentRequestOnFetch(HIUGatewayBaseView):

    def post(self, request, format=None):
        GatewayConsentRequestOnFetchSerializer(data=request.data).is_valid(raise_exception=True)
        self.process_request(request.data)
        return Response(status=HTTP_202_ACCEPTED)

    def process_request(self, request_data):
        with transaction.atomic():
            consent_artefact = HIUConsentArtefact.objects.get(gateway_request_id=request_data["resp"]["requestId"])
            if request_data.get("consent"):
                consent_artefact.details = request_data["consent"]["consentDetail"]
                if consent_artefact.consent_request.artefacts.filter(details__isnull=False).count() == 0:
                    self.update_consent_request_from_artefact(consent_artefact)
            elif request_data.get('error'):
                consent_artefact.status = STATUS_ERROR
                consent_artefact.error = request_data['error']
            consent_artefact.save()

    def update_consent_request_from_artefact(self, consent_artefact):
        consent_request = consent_artefact.consent_request
        consent_request.update_user_amendable_details(consent_artefact.details['permission'],
                                                      consent_artefact.details['hiTypes'])
