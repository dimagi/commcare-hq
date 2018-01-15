from __future__ import absolute_import
import socket

from corehq.motech.repeaters.repeater_generators import BasePayloadGenerator
from custom.icds.const import (
    AADHAAR_NUMBER_CASE_PROPERTY,
    DOB_CASE_PROPERTY,
    GENDER_CASE_PROPERTY,
)
from corehq.apps.hqcase.utils import update_case
from casexml.apps.case.util import get_latest_change_to_case_property

from custom.icds.integrations.uidai.excpetions import AadhaarPayloadException


class AadhaarDemoAuthRepeaterGenerator(BasePayloadGenerator):
    def get_payload(self, repeat_record, person_case):
        server_ip = socket.gethostbyname(socket.gethostname())
        device_id = None
        try:
            last_change_info = get_latest_change_to_case_property(person_case, AADHAAR_NUMBER_CASE_PROPERTY)
            if last_change_info:
                transaction = last_change_info.case_transaction
                device_id = transaction.form.metadata.deviceID
        except AttributeError:
            raise AadhaarPayloadException("Could not determine device ID")
        return {
            'aadhaar_number': person_case.get_case_property(AADHAAR_NUMBER_CASE_PROPERTY),
            'name': person_case.name,
            'dob': person_case.get_case_property(DOB_CASE_PROPERTY),
            'gender': person_case.get_case_property(GENDER_CASE_PROPERTY),
            'ip': server_ip,
            'device_id': device_id
        }

    def handle_success(self, match_result, payload_doc, repeat_record):
        update_case(
            payload_doc.domain,
            payload_doc.case_id,
            {
                "aadhaar_verified": match_result,
            },
        )
