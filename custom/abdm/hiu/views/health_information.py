import json
import time
from datetime import datetime

import requests
from django.core.cache import cache
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.status import HTTP_200_OK, HTTP_202_ACCEPTED

from custom.abdm.auth import ABDMUserAuthentication
from custom.abdm.const import STATUS_ERROR
from custom.abdm.cyrpto import ABDMCrypto
from custom.abdm.exceptions import ABDMServiceUnavailable, ABDMGatewayError
from custom.abdm.hiu.const import GW_HEALTH_INFO_REQUEST_PATH
from custom.abdm.hiu.exceptions import HIU_ERROR_MESSAGES, HIUErrorResponseFormatter
from custom.abdm.hiu.fhir_ui_parser import generate_display_fields_for_bundle
from custom.abdm.hiu.models import HIUConsentArtefact, HIUHealthInformationRequest
from custom.abdm.hiu.serializers.health_information import HIURequestHealthInformationSerializer, \
    HIUReceiveHealthInformationSerializer, GatewayHealthInformationOnRequestSerializer
from custom.abdm.hiu.views.base import HIUBaseView, HIUGatewayBaseView
from custom.abdm.utils import ABDMRequestHelper, abdm_iso_to_datetime


# TODO Check if models required for scenario where multiple pages of data are received
# TODO Refine the use of django cache
# TODO Handle for Links

class RequestHealthInformation(HIUBaseView):
    authentication_classes = [ABDMUserAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        print("RequestHealthInformation", request.query_params)
        return HIUErrorResponseFormatter().generate_custom_error_response(error_code=4451,
                                                                   details_field='artefact_id')
        serializer = HIURequestHealthInformationSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        artefact = self.validate_artefact_expiry(serializer.data['artefact_id'])
        if artefact is False:
            return HIUErrorResponseFormatter().generate_custom_error_response(error_code=4451,
                                                                            details_field='artefact_id')
        # TODO Refactor below
        current_url = request.build_absolute_uri(reverse('request_health_information'))
        request_data = request.query_params
        if request_data.get('transaction_id') and request_data.get('page'):
            health_information_request = HIUHealthInformationRequest.objects.get(transaction_id=
                                                                                 request_data['transaction_id'])
            cache_key = f"{health_information_request.gateway_request_id}_{request_data['page']}"
            data = self.poll_for_data_receipt(cache_key)
            if data:
                return Response(status=HTTP_200_OK, data=self.format_response_data(data, current_url,
                                                                                   artefact.artefact_id))
            else:
                return HIUErrorResponseFormatter().generate_custom_error_response(error_code=4555, status_code=555)
        health_info_url = request.build_absolute_uri(reverse('receive_health_information'))
        gateway_request_data, key_material = self.gateway_health_information_cm_request(artefact, health_info_url)
        self.save_health_info_request(artefact, gateway_request_data, key_material)
        # Wait for health data up to max 1 min
        cache_key = f"{gateway_request_data['requestId']}_1"
        data = self.poll_for_data_receipt(cache_key)
        if data:
            return Response(status=HTTP_200_OK, data=self.format_response_data(data, current_url,
                                                                               artefact.artefact_id))
        else:
            return HIUErrorResponseFormatter().generate_custom_error_response(error_code=4555, status_code=555)

    def _get_next_query_params(self, response_data, artefact_id):
        from django.http import QueryDict
        q = QueryDict('', mutable=True)
        q['artefact_id'] = artefact_id
        q['transaction_id'] = response_data['transactionId']
        q['page'] = response_data['pageNumber'] + 1
        return q

    def format_response_data(self, response_data, current_url, artefact_id):
        # TODO Handle for parsing exception
        # TODO Specs in case of sending directly FHIR data
        # TODO Add a setting for this at the django app level with default to False
        entries = self.parse_fhir_bundle_for_ui(response_data['entries'])
        data = {
            'transaction_id': response_data['transactionId'],
            'page': response_data['pageNumber'],
            'page_count': response_data['pageCount'],
            'next': None,
            'results': entries
        }
        if response_data['pageNumber'] < response_data['pageCount']:
            data['next'] = f'{current_url}?{self._get_next_query_params(response_data, artefact_id).urlencode()}'
        return data

    def validate_artefact_expiry(self, artefact_id):
        # Safety check for artefact expiry as any expired artefact should be deleted through ABDM notification
        artefact = get_object_or_404(HIUConsentArtefact, artefact_id=artefact_id)
        if artefact.consent_request.expiry_date <= datetime.utcnow():
            return False
        return artefact

    def save_health_info_request(self, artefact, gateway_request_data, key_material):
        health_information_request = HIUHealthInformationRequest(consent_artefact=artefact)
        health_information_request.gateway_request_id = gateway_request_data['requestId']
        health_information_request.key_material = key_material.as_dict()
        health_information_request.save()

    def poll_for_data_receipt(self, cache_key):
        # TODO Refine this or use a better approach of subscription if available in RabbitMQ
        attempt = 0
        while attempt <= 20:
            print(f"Checking in cache for {cache_key}")
            data = cache.get(cache_key)
            if data:
                return data
            time.sleep(2)
            attempt += 1
        return False

    def parse_fhir_bundle_for_ui(self, entries):
        # TODO Get health information type and title from Care Context Reference
        from custom.abdm.const import HealthInformationType
        for entry in entries:
            entry['title'] = HealthInformationType.PRESCRIPTION
            entry['content'] = generate_display_fields_for_bundle(entry['content'], HealthInformationType.PRESCRIPTION)
        return entries

    def gateway_health_information_cm_request(self, artefact, health_info_url):
        hiu_crypto = ABDMCrypto()
        request_data = ABDMRequestHelper.common_request_data()
        request_data['hiRequest'] = {'consent': {'id': str(artefact.artefact_id)}}
        request_data['hiRequest']['dateRange'] = artefact.details['permission']['dateRange']
        request_data['hiRequest']['dataPushUrl'] = health_info_url
        request_data['hiRequest']['keyMaterial'] = hiu_crypto.transfer_material
        try:
            ABDMRequestHelper().gateway_post(GW_HEALTH_INFO_REQUEST_PATH, request_data)
        except requests.Timeout:
            raise ABDMServiceUnavailable()
        except requests.HTTPError as err:
            raise ABDMGatewayError(detail=err)
        return request_data, hiu_crypto.key_material


class GatewayHealthInformationOnRequest(HIUGatewayBaseView):

    def post(self, request, format=None):
        print("RequestHealthInformation", request.data)
        GatewayHealthInformationOnRequestSerializer(data=request.data).is_valid(raise_exception=True)
        self.process_request(request.data)
        return Response(status=HTTP_202_ACCEPTED)

    def process_request(self, request_data):
        health_information_request = HIUHealthInformationRequest.objects.get(gateway_request_id=
                                                                             request_data['resp']['requestId'])
        if request_data.get('hiRequest'):
            health_information_request.transaction_id = request_data['hiRequest']['transactionId']
            health_information_request.status = request_data['hiRequest']['sessionStatus']
        elif request_data.get('error'):
            health_information_request.error = request_data['error']
            health_information_request.status = STATUS_ERROR
        health_information_request.save()


class ReceiveHealthInformation(HIUBaseView):

    def post(self, request, format=None):
        print(f"ReceiveHealthInformation {request.data['transactionId']} and page: {request.data['pageCount']}")
        HIUReceiveHealthInformationSerializer(data=request.data).is_valid(raise_exception=True)
        ReceiveHealthInformationProcessor(request.data).process_request()
        return Response(status=HTTP_202_ACCEPTED)


class ReceiveHealthInformationProcessor:
    # TODO Decide if we need to run this in background

    def __init__(self, request_data):
        self.request_data = request_data

    def process_request(self):
        health_information_request = HIUHealthInformationRequest.objects.get(transaction_id=
                                                                             self.request_data['transactionId'])
        return HIUErrorResponseFormatter().generate_custom_error_response(error_code=4410)
        error = self.validate_request(health_information_request.consent_artefact)
        if error:
            return HIUErrorResponseFormatter().generate_custom_error_response(error_code=error['code'])
        decrypted_data = self.decrypt_data(health_information_request)
        cache_key = f"{health_information_request.gateway_request_id}_{self.request_data['pageNumber']}"
        cache.set(cache_key, decrypted_data, 60)

    def validate_request(self, artefact):
        error_code = None
        if artefact is None:
            error_code = 4416
        elif not self._validate_key_material_expiry():
            error_code = 4410
        elif not self._validate_consent_expiry(artefact):
            error_code = 4418
        return {'code': error_code, 'message': HIU_ERROR_MESSAGES.get(error_code)} if error_code else None

    def _validate_key_material_expiry(self):
        key_material_expiry = self.request_data['keyMaterial']['dhPublicKey']['expiry']
        return abdm_iso_to_datetime(key_material_expiry) < datetime.utcnow()

    def _validate_consent_expiry(self, artefact):
        return abdm_iso_to_datetime(artefact.details['permission']['dataEraseAt']) > datetime.utcnow()

    def decrypt_data(self, health_information_request):
        print("Starting data decryption")
        hiu_crypto = ABDMCrypto(key_material_json=health_information_request.key_material)
        hip_transfer_material = self.request_data['keyMaterial']
        decrypted_entries = []
        for entry in self.request_data['entries']:
            data = {'care_context_reference': entry['careContextReference']}
            data['content'] = json.loads(hiu_crypto.decrypt(entry['content'], hip_transfer_material))
            if not hiu_crypto.generate_checksum(data['content']) == entry['checksum']:
                print("Checksum error")
                return False
            decrypted_entries.append(data)
        self.request_data['entries'] = decrypted_entries
        return self.request_data
