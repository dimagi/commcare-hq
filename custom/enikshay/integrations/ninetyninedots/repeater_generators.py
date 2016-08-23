import uuid
import json
import phonenumbers
import jsonobject
from corehq.apps.repeaters.models import RegisterGenerator
from corehq.apps.repeaters.repeater_generators import BasePayloadGenerator

from custom.enikshay.integrations.ninetyninedots.repeaters import NinetyNineDotsRegisterPatientRepeater
from custom.enikshay.case_utils import (
    get_occurrence_case_from_episode,
    get_person_case_from_occurrence,
)


class RegisterPatientPayload(jsonobject.JsonObject):
    beneficiary_id = jsonobject.StringProperty(required=True)
    phone_numbers = jsonobject.StringProperty(required=True)


@RegisterGenerator(NinetyNineDotsRegisterPatientRepeater, 'case_json', 'JSON', is_default=True)
class RegisterPatientPayloadGenerator(BasePayloadGenerator):
    @property
    def content_type(self):
        return 'application/json'

    def get_test_payload(self, domain):
        return json.dumps(RegisterPatientPayload(
            beneficiary_id=uuid.uuid4().hex,
            phone_numbers=_format_number(_parse_number("0123456789"))
        ).to_json())

    def get_payload(self, repeat_record, payload_doc):
        occurence_case = get_occurrence_case_from_episode(payload_doc.domain, payload_doc.case_id)
        person_case = get_person_case_from_occurrence(payload_doc.domain, occurence_case)
        data = RegisterPatientPayload(
            beneficiary_id=person_case.case_id,
            phone_numbers=_get_phone_numbers(person_case)
        )
        return json.dumps(data.to_json())

    def handle_success(self, response, payload_doc):
        pass


def _get_phone_numbers(payload_doc):
    primary_number = _parse_number(payload_doc.dynamic_case_properties().get('mobile_number'))
    backup_number = _parse_number(payload_doc.dynamic_case_properties().get('backup_number'))
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
