import json
import math
from datetime import datetime

import requests
from rest_framework.response import Response
from rest_framework.status import HTTP_202_ACCEPTED

from custom.abdm.const import (
    HEALTH_INFORMATION_MEDIA_TYPE,
    STATUS_ACKNOWLEDGED,
    STATUS_ERROR,
    STATUS_FAILED,
    STATUS_TRANSFERRED, STATUS_DELIVERED, STATUS_ERRORED,
)
from custom.abdm.cyrpto import ABDMCrypto
from custom.abdm.hip.const import (
    GW_HEALTH_INFO_ON_REQUEST_URL,
    GW_HEALTH_INFO_ON_TRANSFER_URL,
    TOTAL_HEALTH_ENTRIES_PER_PAGE,
)
from custom.abdm.hip.exceptions import HIP_ERROR_MESSAGES
from custom.abdm.hip.integrations import get_fhir_data_care_context
from custom.abdm.hip.models import (
    HIPConsentArtefact,
    HIPHealthInformationRequest,
)
from custom.abdm.hip.serializers.health_information import (
    GatewayHealthInformationRequestSerializer,
)
from custom.abdm.hip.views.base import HIPGatewayBaseView
from custom.abdm.utils import (
    GatewayRequestHelper,
    abdm_iso_to_datetime,
)


# TODO For multiple pages check if need to save in Database
# TODO Error Handling/Status Update in case of failed transfers
# TODO General Refactoring and Error Handling


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
        # TODO Check for key material expiry
        artefact = self.fetch_artefact(artefact_id)
        error = self.validate_artefact(artefact, request_data)
        health_information_request = self.save_health_information_request(artefact, request_data, error)
        self.gateway_health_information_on_request(request_data, error)
        if error:
            return error
        transfer_status, care_contexts_status = self.encrypt_and_transfer(artefact.details['careContexts'], request_data)
        health_information_request.update_status(STATUS_TRANSFERRED if transfer_status else STATUS_FAILED)
        self.gateway_health_information_on_transfer(artefact_id, request_data['transactionId'], transfer_status,
                                                    care_contexts_status)

    def encrypt_and_transfer(self, care_contexts, request_data):
        hip_crypto = ABDMCrypto()
        hiu_transfer_material = request_data['hiRequest']['keyMaterial']
        data = {
            "pageCount": int(math.ceil(len(care_contexts)/TOTAL_HEALTH_ENTRIES_PER_PAGE)),
            "transactionId": request_data["transactionId"],
            "keyMaterial": hip_crypto.transfer_material
        }
        care_contexts_status = []
        for index, care_contexts_chunks in enumerate(self._generate_chunks(care_contexts,
                                                                           TOTAL_HEALTH_ENTRIES_PER_PAGE)):
            data['pageNumber'] = index + 1
            data['entries'] = self.get_encrypted_entries(care_contexts_chunks, hiu_transfer_material, hip_crypto)
            transfer_status = self.transfer_data_to_hiu(request_data["hiRequest"]["dataPushUrl"], data)
            care_contexts_status.extend(self._care_contexts_transfer_status(care_contexts_chunks, transfer_status))
        transfer_status = not any(status['hiStatus'] == STATUS_ERRORED for status in care_contexts_status)
        return transfer_status, care_contexts_status

    def _care_contexts_transfer_status(self, care_contexts_chunks, transfer_status):
        hi_status = STATUS_DELIVERED if transfer_status else STATUS_ERRORED
        return [{'careContextReference': care_context['careContextReference'], 'hiStatus': hi_status}
                for care_context in care_contexts_chunks]

    def _generate_chunks(self, data, count):
        assert type(data) == list
        for i in range(0, len(data), count):
            yield data[i:i + count]

    def fetch_artefact(self, artefact_id):
        try:
            return HIPConsentArtefact.objects.get(artefact_id=artefact_id)
        except HIPConsentArtefact.DoesNotExist:
            return None

    def validate_artefact(self, artefact, request_data):
        error_code = None
        if artefact is None:
            error_code = 3416
        elif not self.validate_consent_expiry(artefact, request_data):
            error_code = 3418
        elif not self.validate_requested_date_range(artefact, request_data):
            error_code = 3419
        return {'code': error_code, 'message': HIP_ERROR_MESSAGES.get(error_code)} if error_code else {}

    def validate_requested_date_range(self, artefact, request_data):
        artefact_from_date = abdm_iso_to_datetime(artefact.details['permission']['dateRange']['from'])
        artefact_to_date = abdm_iso_to_datetime(artefact.details['permission']['dateRange']['to'])
        if not (artefact_from_date <= abdm_iso_to_datetime(request_data['hiRequest']['dateRange']['from']) <= artefact_to_date):
            return False
        if not (artefact_from_date <= abdm_iso_to_datetime(request_data['hiRequest']['dateRange']['to']) <= artefact_to_date):
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

    def get_encrypted_entries(self, care_contexts, hiu_transfer_material, hip_crypto):
        entries = []
        for care_context in care_contexts:
            entry = {'media': HEALTH_INFORMATION_MEDIA_TYPE, 'careContextReference': care_context['careContextReference']}
            fhir_data_str = json.dumps(get_fhir_data_care_context(care_context['careContextReference']))
            entry['checksum'] = hip_crypto.generate_checksum(fhir_data_str)
            entry['content'] = hip_crypto.encrypt(fhir_data_str, hiu_transfer_material)
            entries.append(entry)
        return entries

    def transfer_data_to_hiu(self, url, data):
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

    def gateway_health_information_on_transfer(self, artefact_id, transaction_id, transfer_status,
                                               care_contexts_status):
        request_data = GatewayRequestHelper.common_request_data()
        request_data['notification'] = {'consent_id': artefact_id, 'transaction_id': transaction_id,
                                        "doneAt": datetime.utcnow().isoformat()}
        request_data['notification']["notifier"] = {"type": "HIP", "id": 6004}
        session_status = STATUS_TRANSFERRED if transfer_status else STATUS_FAILED
        request_data['notification']["statusNotification"] = {"sessionStatus": session_status, "hipId": 6004}
        request_data['notification']["statusNotification"]["statusResponses"] = care_contexts_status
        GatewayRequestHelper().post(GW_HEALTH_INFO_ON_TRANSFER_URL, request_data)
