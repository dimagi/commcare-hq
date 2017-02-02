import uuid
import json
import phonenumbers
import jsonobject
from corehq.apps.repeaters.repeater_generators import BasePayloadGenerator, RegisterGenerator
from custom.enikshay.integrations.ninetyninedots.repeaters import (
    NinetyNineDotsRegisterPatientRepeater,
    NinetyNineDotsUpdatePatientRepeater,
)
from custom.enikshay.case_utils import (
    get_occurrence_case_from_episode,
    get_person_case_from_occurrence,
    get_open_episode_case_from_person,
    update_case,
)
from custom.enikshay.const import PRIMARY_PHONE_NUMBER, BACKUP_PHONE_NUMBER
from custom.enikshay.exceptions import ENikshayCaseNotFound


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

    def get_payload(self, repeat_record, episode_case):
        occurence_case = get_occurrence_case_from_episode(episode_case.domain, episode_case.case_id)
        person_case = get_person_case_from_occurrence(episode_case.domain, occurence_case)
        person_case_properties = person_case.dynamic_case_properties()
        data = PatientPayload(
            beneficiary_id=person_case.case_id,
            phone_numbers=_get_phone_numbers(person_case_properties),
            merm_id=person_case_properties.get('merm_id', None),
        )
        return json.dumps(data.to_json())

    def handle_success(self, response, episode_case, repeat_record):
        if response.status_code == 201:
            update_case(
                episode_case.domain,
                episode_case.case_id,
                {
                    "dots_99_registered": "true",
                    "dots_99_error": ""
                }
            )

    def handle_failure(self, response, episode_case, repeat_record):
        if 400 <= response.status_code <= 500:
            update_case(
                episode_case.domain,
                episode_case.case_id,
                {
                    "dots_99_registered": (
                        "false"
                        if episode_case.dynamic_case_properties().get('dots_99_registered') != 'true'
                        else 'true'
                    ),
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

    def get_payload(self, repeat_record, person_case):
        person_case_properties = person_case.dynamic_case_properties()
        data = PatientPayload(
            beneficiary_id=person_case.case_id,
            phone_numbers=_get_phone_numbers(person_case_properties),
            merm_id=person_case_properties.get('merm_id', None),
        )
        return json.dumps(data.to_json())

    def handle_success(self, response, person_case, repeat_record):
        try:
            episode_case = get_open_episode_case_from_person(person_case.domain, person_case.case_id)
        except ENikshayCaseNotFound as e:
            self.handle_exception(e, repeat_record)

        if response.status_code == 200:
            update_case(
                episode_case.domain,
                episode_case.case_id,
                {
                    "dots_99_error": ""
                }
            )

    def handle_failure(self, response, person_case, repeat_record):
        try:
            episode_case = get_open_episode_case_from_person(person_case.domain, person_case.case_id)
        except ENikshayCaseNotFound as e:
            self.handle_exception(e, repeat_record)

        if 400 <= response.status_code <= 500:
            update_case(
                episode_case.domain,
                episode_case.case_id,
                {
                    "dots_99_error": "{}: {}".format(
                        response.status_code,
                        response.json().get('error')
                    ),
                }
            )


def _get_phone_numbers(case_properties):
    primary_number = _parse_number(case_properties.get(PRIMARY_PHONE_NUMBER))
    backup_number = _parse_number(case_properties.get(BACKUP_PHONE_NUMBER))
    if primary_number and backup_number:
        return ", ".join([_format_number(primary_number), _format_number(backup_number)])
    elif primary_number:
        return _format_number(primary_number)
    elif backup_number:
        return _format_number(backup_number)


def _parse_number(number):
    if number:
        return phonenumbers.parse(number, "IN")


def _format_number(phonenumber):
    if phonenumber:
        return phonenumbers.format_number(
            phonenumber,
            phonenumbers.PhoneNumberFormat.INTERNATIONAL
        ).replace(" ", "")
