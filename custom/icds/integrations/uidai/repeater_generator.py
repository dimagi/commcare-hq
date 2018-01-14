from __future__ import absolute_import
import socket

from corehq.motech.repeaters.repeater_generators import BasePayloadGenerator
from custom.icds.const import (
    AADHAAR_NUMBER_CASE_PROPERTY,
    DOB_CASE_PROPERTY,
    GENDER_CASE_PROPERTY,
)
from corehq.apps.hqcase.utils import update_case


class AadhaarDemoAuthRepeaterGenerator(BasePayloadGenerator):
    def get_payload(self, repeat_record, person_case):
        server_ip = socket.gethostbyname(socket.gethostname())
        last_case_action = person_case.get_form_transactions()[-1]
        try:
            device_id = last_case_action.form.metadata.deviceID
        except AttributeError as e:
            pass
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