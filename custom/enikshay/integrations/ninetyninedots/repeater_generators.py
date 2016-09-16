import uuid
import json
import phonenumbers
import jsonobject
from corehq.apps.repeaters.repeater_generators import BasePayloadGenerator, RegisterGenerator

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.util import post_case_blocks
from custom.enikshay.integrations.ninetyninedots.repeaters import (
    NinetyNineDotsRegisterPatientRepeater,
    NinetyNineDotsUpdatePatientRepeater,
)
from custom.enikshay.case_utils import (
    get_occurrence_case_from_episode,
    get_person_case_from_occurrence,
)


class PatientPayload(jsonobject.JsonObject):
    beneficiary_id = jsonobject.StringProperty(required=True)
    phone_numbers = jsonobject.StringProperty(required=False)
    merm_id = jsonobject.StringProperty(required=False)


@RegisterGenerator(NinetyNineDotsRegisterPatientRepeater, 'case_json', 'JSON', is_default=True)
class RegisterPatientPayloadGenerator(BasePayloadGenerator):
    @property
    def content_type(self):
        return 'application/json'

    def get_test_payload(self, domain):
        return json.dumps(PatientPayload(
            beneficiary_id=uuid.uuid4().hex,
            phone_numbers=_format_number(_parse_number("0123456789")),
            merm_id=uuid.uuid4().hex,
        ).to_json())

    def get_payload(self, repeat_record, payload_doc):
        occurence_case = get_occurrence_case_from_episode(payload_doc.domain, payload_doc.case_id)
        person_case = get_person_case_from_occurrence(payload_doc.domain, occurence_case)
        person_case_properties = person_case.dynamic_case_properties()
        data = PatientPayload(
            beneficiary_id=person_case.case_id,
            phone_numbers=_get_phone_numbers(person_case_properties),
            merm_id=person_case_properties.get('merm_id', None),
        )
        return json.dumps(data.to_json())

    def handle_success(self, response, payload_doc):
        if response.status_code == 201:
            _update_episode_case(
                payload_doc.domain,
                payload_doc.case_id,
                {
                    "dots_99_registered": "true",
                    "dots_99_error": ""
                }
            )

    def handle_failure(self, response, payload_doc):
        if 400 <= response.status_code <= 500:
            _update_episode_case(
                payload_doc.domain,
                payload_doc.case_id,
                {
                    "dots_99_registered": "false",
                    "dots_99_error": "{}: {}".format(
                        response.status_code,
                        response.json().get('error')
                    ),
                }
            )


@RegisterGenerator(NinetyNineDotsUpdatePatientRepeater, 'case_json', 'JSON', is_default=True)
class UpdatePatientPayloadGenerator(BasePayloadGenerator):
    @property
    def content_type(self):
        return 'application/json'

    def get_test_payload(self, domain):
        return json.dumps(PatientPayload(
            beneficiary_id=uuid.uuid4().hex,
            phone_numbers=_format_number(_parse_number("0123456789"))
        ).to_json())

    def get_payload(self, repeat_record, payload_doc):
        data = PatientPayload(
            beneficiary_id=payload_doc,
            phone_numbers=_get_phone_numbers(payload_doc)
        )
        return json.dumps(data.to_json())

    def handle_success(self, response, payload_doc):
        if response.status_code == 200:
            _update_episode_case(
                payload_doc.domain,
                payload_doc.case_id,
                {
                    "dots_99_error": ""
                }
            )

    def handle_failure(self, response, payload_doc):
        if 400 <= response.status_code <= 500:
            _update_episode_case(
                payload_doc.domain,
                payload_doc.case_id,
                {
                    "dots_99_error": "{}: {}".format(
                        response.status_code,
                        response.json().get('error')
                    ),
                }
            )


def _update_episode_case(domain, case_id, updated_properties):
    post_case_blocks(
        [CaseBlock(
            case_id=case_id,
            update=updated_properties
        ).as_xml()],
        {'domain': domain}
    )


def _get_phone_numbers(case_properties):
    primary_number = _parse_number(case_properties.get('mobile_number'))
    backup_number = _parse_number(case_properties.get('backup_number'))
    if backup_number is not None:
        return ", ".join([_format_number(primary_number), _format_number(backup_number)])
    return _format_number(primary_number)


def _parse_number(number):
    if number is not None:
        return phonenumbers.parse(number, "IN")


def _format_number(phonenumber):
    if phonenumber is not None:
        return phonenumbers.format_number(
            phonenumber,
            phonenumbers.PhoneNumberFormat.INTERNATIONAL
        ).replace(" ", "")
