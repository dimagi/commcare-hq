import json
import math
from datetime import datetime

import requests
from rest_framework.response import Response
from rest_framework.status import HTTP_202_ACCEPTED

from custom.abdm.const import (
    HEALTH_INFORMATION_MEDIA_TYPE,
    STATUS_ACKNOWLEDGED,
    STATUS_DELIVERED,
    STATUS_ERROR,
    STATUS_ERRORED,
    STATUS_FAILED,
    STATUS_TRANSFERRED,
)
from custom.abdm.cyrpto import ABDMCrypto
from custom.abdm.hip.const import (
    GW_HEALTH_INFO_ON_REQUEST_URL,
    GW_HEALTH_INFO_ON_TRANSFER_URL,
    TOTAL_HEALTH_ENTRIES_PER_PAGE,
)
from custom.abdm.hip.exceptions import HIP_ERROR_MESSAGES
from custom.abdm.hip.integrations import get_fhir_data_from_hrp
from custom.abdm.hip.models import (
    HIPConsentArtefact,
    HIPHealthInformationRequest,
)
from custom.abdm.hip.serializers.health_information import (
    GatewayHealthInformationRequestSerializer,
)
from custom.abdm.hip.tasks import process_health_information_request
from custom.abdm.hip.views.base import HIPGatewayBaseView
from custom.abdm.utils import ABDMRequestHelper, abdm_iso_to_datetime


# TODO For multiple pages check if need to save in Database
# TODO Error Handling/Status Update in case of failed transfers
# TODO General Refactoring and Error Handling

# TODO For All Gateway calls, handle http error
# TODO For all background jobs, handle any error in general


class GatewayHealthInformationRequest(HIPGatewayBaseView):

    def post(self, request, format=None):
        print(f"GatewayHealthInformationRequest : {request.data}")
        GatewayHealthInformationRequestSerializer(data=request.data).is_valid(raise_exception=True)
        process_health_information_request.delay(request.data)
        return Response(status=HTTP_202_ACCEPTED)


class GatewayHealthInformationRequestProcessor:

    def __init__(self, request_data):
        self.request_data = request_data

    def process_request(self):
        artefact = self.fetch_artefact()
        error = self.validate_request(artefact)
        health_information_request = self.save_health_information_request(artefact, error)
        self.gateway_health_information_on_request(error)
        if not error:
            transfer_status, care_contexts_wise_status = self.share_health_data(artefact.details['careContexts'])
            health_information_request.update_status(STATUS_TRANSFERRED if transfer_status else STATUS_FAILED)
            self.gateway_health_information_on_transfer(artefact.artefact_id,
                                                        transfer_status,
                                                        care_contexts_wise_status)

    def fetch_artefact(self):
        artefact_id = self.request_data['hiRequest']['consent']['id']
        try:
            return HIPConsentArtefact.objects.get(artefact_id=artefact_id)
        except HIPConsentArtefact.DoesNotExist:
            return None

    def validate_request(self, artefact):
        error_code = None
        if artefact is None:
            error_code = 3416
        elif not self._validate_key_material_expiry():
            error_code = 3410
        elif not self._validate_consent_expiry(artefact):
            error_code = 3418
        elif not self._validate_requested_date_range(artefact):
            error_code = 3419
        return {'code': error_code, 'message': HIP_ERROR_MESSAGES.get(error_code)} if error_code else None

    def _validate_key_material_expiry(self):
        key_material_expiry = self.request_data['hiRequest']['keyMaterial']['dhPublicKey']['expiry']
        return abdm_iso_to_datetime(key_material_expiry) < datetime.utcnow()

    def _validate_consent_expiry(self, artefact):
        return abdm_iso_to_datetime(artefact.details['permission']['dataEraseAt']) > datetime.utcnow()

    def _validate_requested_date_range(self, artefact):
        artefact_from_date = abdm_iso_to_datetime(artefact.details['permission']['dateRange']['from'])
        artefact_to_date = abdm_iso_to_datetime(artefact.details['permission']['dateRange']['to'])
        requested_from_date = abdm_iso_to_datetime(self.request_data['hiRequest']['dateRange']['from'])
        requested_to_date = abdm_iso_to_datetime(self.request_data['hiRequest']['dateRange']['to'])
        if not (artefact_from_date <= requested_from_date <= artefact_to_date):
            return False
        if not (artefact_from_date <= requested_to_date <= artefact_to_date):
            return False
        return True

    def save_health_information_request(self, artefact, error):
        health_information_request = HIPHealthInformationRequest(consent_artefact=artefact,
                                                                 transaction_id=self.request_data['transactionId'],
                                                                 error=error)
        health_information_request.status = STATUS_ERROR if error else STATUS_ACKNOWLEDGED
        health_information_request.save()
        return health_information_request

    def gateway_health_information_on_request(self, error=None):
        request_body = ABDMRequestHelper.common_request_data()
        if error:
            request_body['error'] = error
        else:
            request_body['hiRequest'] = {'transactionId': self.request_data['transactionId'],
                                         'sessionStatus': STATUS_ACKNOWLEDGED}
        request_body['resp'] = {'requestId': self.request_data['requestId']}
        ABDMRequestHelper().gateway_post(GW_HEALTH_INFO_ON_REQUEST_URL, request_body)

    def share_health_data(self, care_contexts):
        hip_crypto = ABDMCrypto()
        hiu_transfer_material = self.request_data['hiRequest']['keyMaterial']
        data = {
            "pageCount": int(math.ceil(len(care_contexts)/TOTAL_HEALTH_ENTRIES_PER_PAGE)),
            "transactionId": self.request_data["transactionId"],
            "keyMaterial": hip_crypto.transfer_material
        }
        care_contexts_wise_status = []
        for index, care_contexts_chunks in enumerate(self._generate_chunks(care_contexts,
                                                                           TOTAL_HEALTH_ENTRIES_PER_PAGE)):
            data['pageNumber'] = index + 1
            data['entries'] = self.get_encrypted_entries(care_contexts_chunks, hiu_transfer_material, hip_crypto)
            transfer_status = self.transfer_data_to_hiu(self.request_data["hiRequest"]["dataPushUrl"], data)
            care_contexts_wise_status.extend(self._care_contexts_transfer_status(care_contexts_chunks, transfer_status))
        transfer_status = not any(status['hiStatus'] == STATUS_ERRORED for status in care_contexts_wise_status)
        return transfer_status, care_contexts_wise_status

    def _generate_chunks(self, data, count):
        assert type(data) == list
        for i in range(0, len(data), count):
            yield data[i:i + count]

    def get_encrypted_entries(self, care_contexts, hiu_transfer_material, hip_crypto):
        entries = []
        for care_context in care_contexts:
            entry = {'media': HEALTH_INFORMATION_MEDIA_TYPE,
                     'careContextReference': care_context['careContextReference']}
            fhir_data_str = json.dumps(get_fhir_data_from_hrp(care_context['careContextReference']))
            entry['checksum'] = hip_crypto.generate_checksum(fhir_data_str)
            entry['content'] = hip_crypto.encrypt(fhir_data_str, hiu_transfer_material)
            entries.append(entry)
        return entries

    def transfer_data_to_hiu(self, url, data):
        # TODO Log error handling
        print(f"HIP: Transferring data to data push url: {url} provided by HIU and data: {data}")
        try:
            resp = requests.post(url=url, data=json.dumps(data), headers={"Content-Type": "application/json"})
            resp.raise_for_status()
            print("HIP: Health data transfer status code from HIU: ", resp.status_code)
            print("HIP: Health data transfer response from HIU: ", resp.text)
            return True
        except Exception as e:
            print("exception", e)
            return False

    def _care_contexts_transfer_status(self, care_contexts_chunks, transfer_status):
        hi_status = STATUS_DELIVERED if transfer_status else STATUS_ERRORED
        return [{'careContextReference': care_context['careContextReference'], 'hiStatus': hi_status}
                for care_context in care_contexts_chunks]

    def gateway_health_information_on_transfer(self, artefact_id, transfer_status,
                                               care_contexts_status):
        request_data = ABDMRequestHelper.common_request_data()
        request_data['notification'] = {'consent_id': artefact_id,
                                        'transaction_id': self.request_data['transactionId'],
                                        "doneAt": datetime.utcnow().isoformat()}
        request_data['notification']["notifier"] = {"type": "HIP", "id": 6004}
        session_status = STATUS_TRANSFERRED if transfer_status else STATUS_FAILED
        request_data['notification']["statusNotification"] = {"sessionStatus": session_status, "hipId": 6004}
        request_data['notification']["statusNotification"]["statusResponses"] = care_contexts_status
        ABDMRequestHelper().gateway_post(GW_HEALTH_INFO_ON_TRANSFER_URL, request_data)
