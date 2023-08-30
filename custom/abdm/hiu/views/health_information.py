import json
from datetime import datetime, timedelta
import time
import requests
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.status import HTTP_200_OK, HTTP_202_ACCEPTED

from custom.abdm.auth import ABDMUserAuthentication
from custom.abdm.const import STATUS_ERROR, CRYPTO_ALGORITHM, CURVE
from custom.abdm.encryption_util import compute_shared_key, calculate_salt_iv, compute_aes_key, decrypt
from custom.abdm.encryption_util2 import getEcdhKeyMaterial, decryptData
from custom.abdm.exceptions import ABDMServiceUnavailable, ABDMGatewayError
from custom.abdm.hiu.const import GW_HEALTH_INFO_REQUEST_PATH
from custom.abdm.hiu.exceptions import send_custom_error_response
from custom.abdm.hiu.models import HIUConsentArtefact, HIUHealthInformationRequest
from custom.abdm.hiu.serializers.health_information import HIURequestHealthInformationSerializer, \
    HIUReceiveHealthInformationSerializer, GatewayHealthInformationOnRequestSerializer
from custom.abdm.hiu.views.base import HIUBaseView, HIUGatewayBaseView
from custom.abdm.utils import GatewayRequestHelper
from django.core.cache import cache
# TODO Scenario where multiple pages of data are received


class RequestHealthInformation(HIUBaseView):
    authentication_classes = [ABDMUserAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        print("RequestHealthInformation", request.query_params)
        serializer = HIURequestHealthInformationSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        artefact = self.validate_artefact_expiry(serializer.data['artefact_id'])
        if artefact is False:
            return send_custom_error_response(error_code=4451, details_field='artefact_id')
        health_info_url = request.build_absolute_uri(reverse('receive_health_information'))
        gateway_request_data, key_material = self.gateway_health_information_cm_request(artefact, health_info_url)
        self.save_health_info_request(artefact, gateway_request_data, key_material)
        # Wait for health data up to max 1 min
        data = self.poll_for_data_receipt(gateway_request_data['requestId'])
        if data:
            return Response(status=HTTP_200_OK, data=data)
        else:
            return Response(status=HTTP_200_OK, data= {"data": "No data"})

    def validate_artefact_expiry(self, artefact_id):
        # Safety check for artefact expiry as any expired artefact should be deleted through ABDM notification
        artefact = get_object_or_404(HIUConsentArtefact, artefact_id=artefact_id)
        if artefact.consent_request.expiry_date <= datetime.utcnow():
            return False
        return artefact

    def save_health_info_request(self, artefact, gateway_request_data, key_material):
        health_information_request = HIUHealthInformationRequest(consent_artefact=artefact)
        health_information_request.gateway_request_id = gateway_request_data['requestId']
        health_information_request.key_material = key_material
        health_information_request.save()

    def poll_for_data_receipt(self, gateway_request_id):
        # TODO Poll continuously for data receipt or subscribe if possible
        attempt = 0
        while attempt <= 20:
            print(f"Checking in cache for {gateway_request_id}")
            data = cache.get(gateway_request_id)
            if data:
                print("Found data in cache")
                return data
            time.sleep(2)
            attempt += 1
        print("Data not found. Time expired")
        return False

    def decrypt_data(self):
        # TODO Decrypt data and create appropriate response body
        pass

    def parse_health_data(self):
        # TODO Parse required data from the HI Type received
        pass

    def _hiu_key_material_transfer(self, hiu_key_material):
        return {
            "cryptoAlg": CRYPTO_ALGORITHM,
            "curve": CURVE,
            "dhPublicKey": {
                "expiry": (datetime.utcnow() + timedelta(days=10)).isoformat(),
                "parameters": "Curve25519",
                "keyValue": hiu_key_material['publicKey']
            },
            "nonce": hiu_key_material['nonce']
        }

    def gateway_health_information_cm_request(self, artefact, health_info_url):
        request_data = GatewayRequestHelper.common_request_data()
        request_data['hiRequest'] = {'consent': {'id': str(artefact.artefact_id)}}
        request_data['hiRequest']['dateRange'] = artefact.details['permission']['dateRange']
        request_data['hiRequest']['dataPushUrl'] = health_info_url
        key_material = getEcdhKeyMaterial()
        request_data['hiRequest']['keyMaterial'] = self._hiu_key_material_transfer(key_material)
        try:
            GatewayRequestHelper().post(GW_HEALTH_INFO_REQUEST_PATH, request_data)
        except requests.Timeout:
            raise ABDMServiceUnavailable()
        except requests.HTTPError as err:
            raise ABDMGatewayError(detail=err)
        return request_data, key_material


class GatewayHealthInformationOnRequest(HIUGatewayBaseView):
    # authentication_classes = [ABDMUserAuthentication]
    # permission_classes = [IsAuthenticated]

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
        print(f"ReceiveHealthInformation {request.data}")
        HIUReceiveHealthInformationSerializer(data=request.data).is_valid(raise_exception=True)
        self.process_request(request.data)
        return Response(status=HTTP_202_ACCEPTED)

    def process_request(self, request_data):
        # TODO Save data received in the cache along with transaction id
        #  so that it can be picked up by pending request from HIU client
        health_information_request = HIUHealthInformationRequest.objects.get(transaction_id=
                                                                             request_data['transactionId'])
        decrypted_entries = self.decrypt_data(request_data, health_information_request)
        cache.set(health_information_request.gateway_request_id, decrypted_entries, 6)

    def decrypt_data(self, request_data, health_information_request):
        # TODO Decrypt data and create appropriate response body
        print("Starting data decryption")
        hiu_key_material = health_information_request.key_material
        hip_key_material = request_data['keyMaterial']
        # shared_key = compute_shared_key(hip_key_material['dhPublicKey']['keyValue'], hiu_key_material['privateKey'])
        # salt, iv = calculate_salt_iv(hip_key_material['nonce'], hiu_key_material['nonce'])
        # aes_key = compute_aes_key(salt, shared_key)
        decrypted_entries = []
        for entry in request_data["entries"]:
            data = decryptData({
                'encryptedData': entry['content'],
                'requesterNonce': hiu_key_material['nonce'],
                'senderNonce': hip_key_material['nonce'],
                'requesterPrivateKey': hiu_key_material['privateKey'],
                'senderPublicKey': hip_key_material['dhPublicKey']['keyValue']
            })['decryptedData']
            decrypted_entries.append(json.loads(data))
            # TODO Test for checksum
        print(f"Data decryption performed successfully - {decrypted_entries}")
        return decrypted_entries
