import uuid
from datetime import datetime
from rest_framework.exceptions import APIException

import requests
from rest_framework import viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.status import HTTP_202_ACCEPTED, HTTP_200_OK, HTTP_400_BAD_REQUEST, HTTP_504_GATEWAY_TIMEOUT
from rest_framework.views import APIView

from custom.abdm.const import ADDITIONAL_HEADERS, STATUS_REQUESTED, STATUS_GRANTED, STATUS_ERROR, STATUS_REVOKED, \
    STATUS_EXPIRED
from custom.abdm.hiu.const import GW_CONSENT_REQUEST_INIT_PATH, GW_CONSENTS_FETCH_PATH, \
    GW_CONSENT_REQUEST_ON_NOTIFY_PATH
from custom.abdm.hiu.models import HIUConsentRequest, HIUConsentArtefact
from custom.abdm.hiu.serializers import (
    GenerateConsentSerializer,
    HIUConsentRequestSerializer, HIUConsentArtefactSerializer, RequestBaseSerializer,
)
from custom.abdm.utils import get_response_http_post, StandardResultsSetPagination
from custom.abdm.hiu.errors import hiu_exception_handler, ABDMServiceUnavailable, ABDMGatewayError
from custom.abdm.auth import ABDMUserAuthentication
from rest_framework.permissions import IsAuthenticated


class GenerateConsent(APIView):
    authentication_classes = [ABDMUserAuthentication]
    permission_classes = [IsAuthenticated]

    def get_exception_handler(self):
        return hiu_exception_handler

    def post(self, request, format=None):
        print("GenerateConsent: ", request.data)
        # TODO Update Serializer
        serializer = GenerateConsentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        consent_data = serializer.data
        # TODO Handling of HIU ID (This is decided to be done later)
        # consent_data["hiu"] = {
        #     'id': 'Ashish-HIU-Registered'
        # }
        request_id = str(uuid.uuid4())
        self.gateway_consent_request_init(request_id, consent_data)
        self.save_consent_request(request_id, consent_data)
        return Response(status=HTTP_200_OK)

    def gateway_consent_request_init(self, request_id, consent_data):
        # TODO Write a function to update these two values
        request_data = {"requestId": request_id, "timestamp": str(datetime.utcnow().isoformat()),
                        "consent": consent_data}
        try:
            get_response_http_post(GW_CONSENT_REQUEST_INIT_PATH, {}, ADDITIONAL_HEADERS)
        except requests.Timeout:
            raise ABDMServiceUnavailable()
        except requests.HTTPError as err:
            raise ABDMGatewayError(err)

    def save_consent_request(self, gateway_request_id, consent_data):
        consent_request = HIUConsentRequest()
        consent_request.gateway_request_id = gateway_request_id
        consent_request.details = consent_data
        consent_request.save()


class GatewayConsentRequestOnInit(APIView):

    def post(self, request, format=None):
        print("GatewayConsentRequestOnInit: ", request.data)
        # TODO Validation via serializer
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


class GatewayConsentRequestNotify(APIView):

    def post(self, request, format=None):
        print("GatewayConsentRequestNotify: ", request.data)
        # TODO Validation via serializer
        self.process_request(request.data)
        return Response(status=HTTP_202_ACCEPTED)

    # TODO Background
    def process_request(self, request_data):
        consent_request_id = request_data['notification']['consentRequestId']
        if request_data['notification']['status'] == STATUS_GRANTED:
            consent_request = HIUConsentRequest.objects.get(consent_request_id=consent_request_id)
            self.handle_granted(request_data, consent_request)
        elif request_data['notification']['status'] == STATUS_EXPIRED:
            consent_request = HIUConsentRequest.objects.get(consent_request_id=consent_request_id)
            self.handle_expired(consent_request)
        elif request_data['notification']['status'] == STATUS_REVOKED:
            self.handle_revoked(request_data)
        else:   # Denied
            consent_request = HIUConsentRequest.objects.get(consent_request_id=consent_request_id)
            consent_request.status = request_data['notification']['status']
            consent_request.save()

    def handle_granted(self, request_data, consent_request):
        consent_request.status = STATUS_GRANTED
        consent_request.save()
        for artefact in request_data['notification']['consentArtefacts']:
            hiu_consent_artefact = HIUConsentArtefact(artefact_id=artefact['id'])
            hiu_consent_artefact.consent_request = consent_request
            hiu_consent_artefact.status = STATUS_GRANTED
            hiu_consent_artefact.save()
            self.gateway_fetch_artefact_details(artefact['id'])

    def handle_expired(self, consent_request):
        consent_request.status = STATUS_EXPIRED
        consent_request.save()
        artefact_ids = []
        for artefact in consent_request.artefacts.all():
            artefact.status = STATUS_EXPIRED
            artefact.save()
            artefact_ids.append(artefact.artefact_id)
        self.gateway_consents_on_notify(artefact_ids)

    def handle_revoked(self, request_data):
        artefact_ids = [artefact['id'] for artefact in request_data['notification']['consentArtefacts']]
        for artefact_id in artefact_ids:
            artefact = HIUConsentArtefact.objects.get(artefact_id=artefact_id)
            artefact.status = STATUS_REVOKED
            artefact.save()
        if artefact_ids and artefact:
            consent_request = artefact.consent_request
            if not any(artefact.status != STATUS_REVOKED for artefact in consent_request.artefacts.all()):
                consent_request.status = STATUS_REVOKED
                consent_request.save()
        self.gateway_consents_on_notify(artefact_ids, request_data['requestId'])

    def gateway_fetch_artefact_details(self, artefact_id):
        request_data = {"consentId": artefact_id, "requestId": str(uuid.uuid4()),
                        "timestamp": str(datetime.utcnow().isoformat())}
        # TODO Handle in case of error
        get_response_http_post(GW_CONSENTS_FETCH_PATH, request_data, ADDITIONAL_HEADERS)

    def gateway_consents_on_notify(self, artefact_ids, request_id):
        request_data = {'requestId': str(uuid.uuid4()), 'timestamp': str(datetime.utcnow().isoformat()),
                        'acknowledgement': [{'status': 'OK', 'consentId': artefact_id} for artefact_id in artefact_ids],
                        'resp': {'requestId': request_id}}
        # TODO Handle in case of error
        get_response_http_post(GW_CONSENT_REQUEST_ON_NOTIFY_PATH, request_data, ADDITIONAL_HEADERS)


class GatewayConsentRequestOnFetch(APIView):

    def post(self, request, format=None):
        print("GatewayConsentRequestOnFetch: ", request.data)
        # TODO Validation via serializer
        self.process_request(request.data)
        return Response(status=HTTP_202_ACCEPTED)

    def process_request(self, request_data):
        # TODO Handle if error received
        if request_data.get("consent"):
            consent_artefact = HIUConsentArtefact.objects.get(artefact_id=request_data["consent"]["consentDetail"]["consentId"])
            consent_artefact.details = request_data["consent"]["consentDetail"]
            consent_artefact.save()

    def update_consent_details(self, consent_data):
        pass


# List, Detail
class ConsentFetch(viewsets.ReadOnlyModelViewSet):
    queryset = HIUConsentRequest.objects.all()
    serializer_class = HIUConsentRequestSerializer
    pagination_class = StandardResultsSetPagination
    authentication_classes = [ABDMUserAuthentication]
    # permission_classes = [IsAuthenticated]


class ConsentArtefactFetch(viewsets.ReadOnlyModelViewSet):
    queryset = HIUConsentArtefact.objects.all()
    serializer_class = HIUConsentArtefactSerializer
    pagination_class = StandardResultsSetPagination
    authentication_classes = [ABDMUserAuthentication]
    # permission_classes = [IsAuthenticated]
