import json

from rest_framework.status import HTTP_202_ACCEPTED
import hashlib
from datetime import datetime, timedelta
from custom.abdm.const import CRYPTO_ALGORITHM, CURVE, STATUS_ACKNOWLEDGED, STATUS_TRANSFERRED, STATUS_FAILED, \
    STATUS_ERROR, HEALTH_INFORMATION_MEDIA_TYPE
from custom.abdm.encryption_util import generate_key_material, compute_shared_key, calculate_salt_iv, compute_aes_key, encrypt
from custom.abdm.encryption_util2 import getEcdhKeyMaterial, encryptData
from custom.abdm.hip.const import GW_HEALTH_INFO_ON_TRANSFER_URL, GW_HEALTH_INFO_ON_REQUEST_URL
from custom.abdm.hip.exceptions import HIPErrorResponseFormatter, HIP_ERROR_MESSAGES
from custom.abdm.hip.integrations import fhir_data_care_context
from custom.abdm.hip.models import HIPConsentArtefact, HIPHealthInformationRequest
from custom.abdm.hip.serializers.health_information import GatewayHealthInformationRequestSerializer
from custom.abdm.hip.views.base import HIPGatewayBaseView
from rest_framework.response import Response
from base64 import b64encode

from custom.abdm.utils import GatewayRequestHelper, abdm_iso_to_datetime, generate_checksum


class GatewayHealthInformationRequest(HIPGatewayBaseView):

    def post(self, request, format=None):
        print(f"GatewayHealthInformationRequest : {request.data}")
        GatewayHealthInformationRequestSerializer(data=request.data).is_valid(raise_exception=True)
        # TODO Use Celery
        import threading
        x = threading.Thread(target=self.process_request, args=(request.data,), daemon=True)
        x.start()
        return Response(status=HTTP_202_ACCEPTED)

    def process_request(self, request_data):
        artefact_id = request_data['hiRequest']['consent']['id']
        artefact = self.fetch_artefact(artefact_id)
        error_code = self.perform_validations(artefact, request_data)
        error = {'code': error_code, 'message': HIP_ERROR_MESSAGES.get(error_code)} if error_code else None
        health_information_request = self.save_health_information_request(artefact, request_data, error)
        if error:
            return self.gateway_health_information_on_request(request_data, error)
        self.gateway_health_information_on_request(request_data, {})
        hip_key_material_transfer, entries = self.get_entries(artefact.details['careContexts'],
                                                              request_data['hiRequest']['keyMaterial'])
        request_body = self.format_request_body(request_data, entries, hip_key_material_transfer)
        status = self.transfer_data_to_hiu(request_data["hiRequest"]["dataPushUrl"], request_body)
        self.update_health_information_request(health_information_request, status)
        # self.gateway_health_information_on_transfer(artefact_id, request_data['transactionId'], status, {})

    def perform_validations(self, artefact, request_data):
        error_code = None
        if artefact is None:
            error_code = 3416
        elif self.validate_consent_expiry(artefact, request_data) is False:
            error_code = 3418
        elif self.validate_date_range(artefact, request_data) is False:
            error_code = 3419
        return error_code

    def fetch_artefact(self, artefact_id):
        try:
            return HIPConsentArtefact.objects.get(artefact_id=artefact_id)
        except HIPConsentArtefact.DoesNotExist:
            return None

    def validate_date_range(self, artefact, request_data):
        artefact_from_date = abdm_iso_to_datetime(artefact.details['permission']['dateRange']['from'])
        artefact_to_date = abdm_iso_to_datetime(artefact.details['permission']['dateRange']['to'])
        if not (artefact_from_date <= abdm_iso_to_datetime(request_data['hiRequest']['dateRange']['from']) <= artefact_to_date):
            return False
        if not (artefact_from_date <= abdm_iso_to_datetime(
                request_data['hiRequest']['dateRange']['to']) <= artefact_to_date):
            return False
        return True

    def validate_consent_expiry(self, artefact, request_data):
        return abdm_iso_to_datetime(artefact.details['permission']['dataEraseAt']) > datetime.utcnow()

    def save_health_information_request(self, artefact, request_data, error):
        health_information_request = HIPHealthInformationRequest(consent_artefact=artefact,
                                                                 transaction_id=request_data['transactionId'],
                                                                 error=error)
        health_information_request.status = STATUS_ERROR if error else STATUS_ACKNOWLEDGED
        health_information_request.save()
        return health_information_request

    def gateway_health_information_on_request(self, request_data, error=None):
        request_body = GatewayRequestHelper.common_request_data()
        if error:
            request_body['error'] = error
        else:
            request_body['hiRequest'] = {'transactionId': request_data['transactionId'],
                                         'sessionStatus': STATUS_ACKNOWLEDGED}
        request_body['resp'] = {'requestId': request_data['requestId']}
        GatewayRequestHelper().post(GW_HEALTH_INFO_ON_REQUEST_URL, request_body)

    def get_entries(self, care_contexts, hiu_key_material):
        entries = []
        # TODO Consider moving to utility or maybe create a class for this
        hip_key_material = getEcdhKeyMaterial()
        # shared_key = compute_shared_key(hiu_key_material['dhPublicKey']['keyValue'], hip_key_material['privateKey'])
        # salt, iv = calculate_salt_iv(hip_key_material['nonce'], hiu_key_material['nonce'])
        # aes_key = compute_aes_key(salt, shared_key)
        for care_context in care_contexts:
            entry = {'media': HEALTH_INFORMATION_MEDIA_TYPE, 'careContextReference': care_context['careContextReference']}
            fhir_data = fhir_data_care_context(care_context['careContextReference'])
            fhir_data_str = json.dumps(fhir_data)
            entry['checksum'] = generate_checksum(fhir_data_str)
            entry['content'] = encryptData(
                {
                    'stringToEncrypt': fhir_data_str,
                    'senderNonce': hip_key_material['nonce'],
                    'requesterNonce': hiu_key_material['nonce'],
                    'senderPrivateKey': hip_key_material['privateKey'],
                    'requesterPublicKey': hiu_key_material['dhPublicKey']['keyValue']
                }
            )['encryptedData']
            entries.append(entry)
        hip_key_material_transfer = self._hip_key_material_transfer(hip_key_material)
        return hip_key_material_transfer, entries

    def _hip_key_material_transfer(self, hip_key_material):
        return {
            "cryptoAlg": CRYPTO_ALGORITHM,
            "curve": CURVE,
            "dhPublicKey": {
                "expiry": (datetime.utcnow() + timedelta(days=10)).isoformat(),
                "parameters": "Curve25519",
                "keyValue": hip_key_material['x509PublicKey']
            },
            "nonce": hip_key_material['nonce']
        }

    def format_request_body(self, request_data, entries, hip_key_material_transfer):
        data = {
            "pageNumber": 1,
            "pageCount": 1,
            "transactionId": request_data["transactionId"],
            "entries": entries,
            "keyMaterial": hip_key_material_transfer
        }
        return data

    def transfer_data_to_hiu(self, url, data):
        # TODO Refine and check how to do for multiple pages
        headers = {"Content-Type": "application/json"}
        import requests
        import json
        print(f"HIP: Transferring data to data push url: {url} provided by HIU and data: {data}")
        try:
            resp = requests.post(url=url, data=json.dumps(data), headers=headers)
            resp.raise_for_status()
            print("HIP: Health data transfer status code from HIU: ", resp.status_code)
            print("HIP: Health data transfer response from HIU: ", resp.text)
            return True
        except Exception as e:
            print("exception", e)
            return False

    def gateway_health_information_on_transfer(self, artefact_id, transaction_id, status, care_contexts):
        request_data = GatewayRequestHelper.common_request_data()
        request_data['notification'] = {'consent_id': artefact_id, 'transaction_id': transaction_id,
                                        "doneAt": datetime.utcnow().isoformat()}
        request_data['notification']["notifier"] = {"type": "HIP", "id": 6004}
        session_status = STATUS_TRANSFERRED if status else STATUS_FAILED
        request_data['notification']["statusNotification"] = {"sessionStatus": session_status, "hipId": 6004}
        # TODO Add more params
        GatewayRequestHelper().post(GW_HEALTH_INFO_ON_TRANSFER_URL, request_data)

    def update_health_information_request(self, health_information_request, status):
        health_information_request.status = status
        health_information_request.save()
