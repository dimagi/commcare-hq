import uuid
import json
import phonenumbers
import jsonobject
import pytz

from django.utils.dateparse import parse_datetime

from corehq.apps.repeaters.repeater_generators import (
    BasePayloadGenerator,
    RegisterGenerator,
)
from corehq.apps.repeaters.exceptions import RequestConnectionError
from custom.enikshay.integrations.ninetyninedots.repeaters import (
    NinetyNineDotsRegisterPatientRepeater,
    NinetyNineDotsUpdatePatientRepeater,
    NinetyNineDotsAdherenceRepeater,
    NinetyNineDotsTreatmentOutcomeRepeater,
)
from custom.enikshay.case_utils import (
    get_occurrence_case_from_episode,
    get_person_case_from_occurrence,
    get_open_episode_case_from_person,
    update_case,
    get_person_locations,
    get_episode_case_from_adherence,
    CASE_TYPE_PERSON,
    CASE_TYPE_EPISODE,
)
from custom.enikshay.const import (
    NINETYNINEDOTS_NUMBERS,
    MERM_ID,
    PERSON_FIRST_NAME,
    PERSON_LAST_NAME,
    TREATMENT_START_DATE,
    TREATMENT_SUPPORTER_FIRST_NAME,
    TREATMENT_SUPPORTER_LAST_NAME,
    TREATMENT_SUPPORTER_PHONE,
    TREATMENT_OUTCOME,
    TREATMENT_OUTCOME_DATE,
    WEIGHT_BAND,
    CURRENT_ADDRESS,
    ENROLLED_IN_PRIVATE,
)
from custom.enikshay.exceptions import ENikshayCaseNotFound


class MermParams(jsonobject.JsonObject):
    IMEI = jsonobject.StringProperty(required=False)
    daily_reminder_status = jsonobject.IntegerProperty(required=False, choices=(1, 0), exclude_if_none=True)
    daily_reminder_time = jsonobject.TimeProperty(required=False, exclude_if_none=True)  # HH:mm
    refill_reminder_status = jsonobject.IntegerProperty(required=False, choices=(1, 0), exclude_if_none=True)
    refill_reminder_datetime = jsonobject.DateTimeProperty(
        required=False,
        exact=True,
        exclude_if_none=True
    )  # yy/MM/dd HH:mm:ss
    RT_hours = jsonobject.IntegerProperty(
        required=False,
        exclude_if_none=True
    )  # 1 = 12 hours; i.e. for 3 days - RT_hours = 6


class PatientPayload(jsonobject.JsonObject):
    beneficiary_id = jsonobject.StringProperty(required=True)
    first_name = jsonobject.StringProperty(required=False)
    last_name = jsonobject.StringProperty(required=False)

    state_code = jsonobject.StringProperty(required=False)
    district_code = jsonobject.StringProperty(required=False)
    tu_code = jsonobject.StringProperty(required=False)
    phi_code = jsonobject.StringProperty(required=False, exclude_if_none=True)
    he_code = jsonobject.StringProperty(required=False, exclude_if_none=True)

    phone_numbers = jsonobject.StringProperty(required=False)
    merm_params = jsonobject.ObjectProperty(MermParams, required=False)

    treatment_start_date = jsonobject.StringProperty(required=False)

    treatment_supporter_name = jsonobject.StringProperty(required=False)
    treatment_supporter_phone_number = jsonobject.StringProperty(required=False)

    @classmethod
    def create(cls, person_case, episode_case):
        person_case_properties = person_case.dynamic_case_properties()
        episode_case_properties = episode_case.dynamic_case_properties()
        person_locations = get_person_locations(person_case)
        try:
            locations = dict(
                state_code=person_locations.sto,
                district_code=person_locations.dto,
                tu_code=person_locations.tu,
                phi_code=person_locations.phi,
            )
        except AttributeError:
            locations = dict(
                state_code=person_locations.sto,
                district_code=person_locations.dto,
                tu_code=person_locations.tu,
                he_code=person_locations.pcp,
            )

        merm_params = MermParams(
            IMEI=person_case_properties.get(MERM_ID, None),
        )

        return cls(
            beneficiary_id=person_case.case_id,
            first_name=person_case_properties.get(PERSON_FIRST_NAME, None),
            last_name=person_case_properties.get(PERSON_LAST_NAME, None),
            phone_numbers=_get_phone_numbers(person_case_properties),
            merm_params=merm_params,
            treatment_start_date=episode_case_properties.get(TREATMENT_START_DATE, None),
            treatment_supporter_name=u"{} {}".format(
                episode_case_properties.get(TREATMENT_SUPPORTER_FIRST_NAME, ''),
                episode_case_properties.get(TREATMENT_SUPPORTER_LAST_NAME, ''),
            ),
            treatment_supporter_phone_number=(
                _format_number(
                    _parse_number(episode_case_properties.get(TREATMENT_SUPPORTER_PHONE))
                )
            ),
            weight_band=episode_case_properties.get(WEIGHT_BAND),
            address=person_case_properties.get(CURRENT_ADDRESS),
            sector='private' if person_case_properties.get(ENROLLED_IN_PRIVATE) == 'true' else 'public',
            **locations
        )


class NinetyNineDotsBasePayloadGenerator(BasePayloadGenerator):
    def handle_exception(self, exception, repeat_record):
        if isinstance(exception, RequestConnectionError):
            update_case(repeat_record.domain, repeat_record.payload_id, {
                "dots_99_error": u"RequestConnectionError: {}".format(unicode(exception))
            })


@RegisterGenerator(NinetyNineDotsRegisterPatientRepeater, 'case_json', 'JSON', is_default=True)
class RegisterPatientPayloadGenerator(NinetyNineDotsBasePayloadGenerator):
    @property
    def content_type(self):
        return 'application/json'

    def get_test_payload(self, domain):
        return json.dumps(PatientPayload(
            beneficiary_id=uuid.uuid4().hex,
            phone_numbers=_format_number(_parse_number("0123456789")),
            merm_params=MermParams(
                IMEI=uuid.uuid4().hex,
            )
        ).to_json())

    def get_payload(self, repeat_record, episode_case):
        occurence_case = get_occurrence_case_from_episode(episode_case.domain, episode_case.case_id)
        person_case = get_person_case_from_occurrence(episode_case.domain, occurence_case)
        return json.dumps(PatientPayload.create(person_case, episode_case).to_json())

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
class UpdatePatientPayloadGenerator(NinetyNineDotsBasePayloadGenerator):
    @property
    def content_type(self):
        return 'application/json'

    def get_test_payload(self, domain):
        return json.dumps(PatientPayload(
            beneficiary_id=uuid.uuid4().hex,
            phone_numbers=_format_number(_parse_number("0123456789"))
        ).to_json())

    def _get_cases(self, episode_or_person):
        if episode_or_person.type == CASE_TYPE_PERSON:
            person_case = episode_or_person
            episode_case = get_open_episode_case_from_person(person_case.domain, person_case.case_id)
        elif episode_or_person.type == CASE_TYPE_EPISODE:
            episode_case = episode_or_person
            occurrence_case = get_occurrence_case_from_episode(episode_case.domain, episode_case.case_id)
            person_case = get_person_case_from_occurrence(episode_case.domain, occurrence_case.case_id)
        else:
            raise ENikshayCaseNotFound("wrong case passed to repeater")
        return person_case, episode_case

    def get_payload(self, repeat_record, episode_or_person):
        person_case, episode_case = self._get_cases(episode_or_person)
        return json.dumps(PatientPayload.create(person_case, episode_case).to_json())

    def handle_success(self, response, episode_or_person, repeat_record):
        try:
            person_case, episode_case = self._get_cases(episode_or_person)
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

    def handle_failure(self, response, episode_or_person, repeat_record):
        try:
            person_case, episode_case = self._get_cases(episode_or_person)
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


@RegisterGenerator(NinetyNineDotsAdherenceRepeater, 'case_json', 'JSON', is_default=True)
class AdherencePayloadGenerator(NinetyNineDotsBasePayloadGenerator):

    def get_payload(self, repeat_record, adherence_case):
        domain = adherence_case.domain
        person_case = get_person_case_from_occurrence(
            domain, get_occurrence_case_from_episode(
                domain, get_episode_case_from_adherence(domain, adherence_case.case_id).case_id
            ).case_id
        )
        adherence_case_properties = adherence_case.dynamic_case_properties()
        date = (parse_datetime(adherence_case.dynamic_case_properties().get('adherence_date'))
                .astimezone(pytz.timezone('Asia/Kolkata'))
                .date())
        payload = {
            'beneficiary_id': person_case.case_id,
            'adherence_date': date.isoformat(),
            'adherence_source': adherence_case_properties.get('adherence_source'),
            'adherence_value': adherence_case_properties.get('adherence_value'),
        }
        return json.dumps(payload)

    def handle_success(self, response, adherence_case, repeat_record):
        if response.status_code == 200:
            update_case(
                adherence_case.domain,
                adherence_case.case_id,
                {
                    "dots_99_updated": "true",
                    "dots_99_error": ""
                }
            )

    def handle_failure(self, response, adherence_case, repeat_record):
        if 400 <= response.status_code <= 500:
            update_case(
                adherence_case.domain,
                adherence_case.case_id,
                {
                    "dots_99_updated": (
                        "false"
                        if adherence_case.dynamic_case_properties().get('dots_99_updated') != 'true'
                        else 'true'
                    ),
                    "dots_99_error": "{}: {}".format(
                        response.status_code,
                        response.json().get('error')
                    ),
                }
            )


@RegisterGenerator(NinetyNineDotsTreatmentOutcomeRepeater, 'case_json', 'JSON', is_default=True)
class TreatmentOutcomePayloadGenerator(NinetyNineDotsBasePayloadGenerator):

    def get_payload(self, repeat_record, episode_case):
        domain = episode_case.domain
        person_case = get_person_case_from_occurrence(
            domain, get_occurrence_case_from_episode(
                domain, episode_case.case_id
            ).case_id
        )
        episode_case_properties = episode_case.dynamic_case_properties()
        payload = {
            'beneficiary_id': person_case.case_id,
            'end_date': episode_case_properties.get(TREATMENT_OUTCOME_DATE),
            'treatment_outcome': episode_case_properties.get(TREATMENT_OUTCOME),
        }
        return json.dumps(payload)

    def handle_success(self, response, episode_case, repeat_record):
        if response.status_code == 200:
            update_case(
                episode_case.domain,
                episode_case.case_id,
                {
                    "dots_99_treatment_outcome_updated": "true",
                    "dots_99_error": ""
                }
            )

    def handle_failure(self, response, episode_case, repeat_record):
        if 400 <= response.status_code <= 500:
            update_case(
                episode_case.domain,
                episode_case.case_id,
                {
                    "dots_99_treatment_outcome_updated": (
                        "false"
                        if episode_case.dynamic_case_properties().get('dots_99_updated') != 'true'
                        else 'true'
                    ),
                    "dots_99_error": "{}: {}".format(
                        response.status_code,
                        response.json().get('error')
                    ),
                }
            )


def _get_phone_numbers(case_properties):
    numbers = []
    for potential_number in NINETYNINEDOTS_NUMBERS:
        number = _parse_number(case_properties.get(potential_number))
        if number:
            numbers.append(_format_number(number))
    return ", ".join(numbers) if numbers else None


def _parse_number(number):
    if number:
        return phonenumbers.parse(number, "IN")


def _format_number(phonenumber):
    if phonenumber:
        return phonenumbers.format_number(
            phonenumber,
            phonenumbers.PhoneNumberFormat.INTERNATIONAL
        ).replace(" ", "")
