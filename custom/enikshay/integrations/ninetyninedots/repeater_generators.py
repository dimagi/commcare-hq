from __future__ import absolute_import

import json

import six
from django.utils.dateparse import parse_date

from corehq.motech.repeaters.exceptions import RequestConnectionError
from corehq.motech.repeaters.repeater_generators import BasePayloadGenerator
from custom.enikshay.case_utils import (
    CASE_TYPE_EPISODE,
    CASE_TYPE_PERSON,
    get_occurrence_case_from_episode,
    get_open_episode_case_from_person,
    get_person_case,
    get_person_case_from_occurrence,
    update_case,
)
from custom.enikshay.const import TREATMENT_OUTCOME, TREATMENT_OUTCOME_DATE
from custom.enikshay.exceptions import ENikshayCaseNotFound
from custom.enikshay.integrations.ninetyninedots.api_spec import \
    get_patient_payload


class NinetyNineDotsBasePayloadGenerator(BasePayloadGenerator):
    @property
    def content_type(self):
        return 'application/json'

    def handle_exception(self, exception, repeat_record):
        if isinstance(exception, RequestConnectionError):
            update_case(repeat_record.domain, repeat_record.payload_id, {
                "dots_99_error": u"RequestConnectionError: {}".format(six.text_type(exception))
            })


class RegisterPatientPayloadGenerator(NinetyNineDotsBasePayloadGenerator):
    deprecated_format_names = ('case_json',)

    def get_payload(self, repeat_record, episode_case):
        occurrence_case = get_occurrence_case_from_episode(episode_case.domain, episode_case.case_id)
        person_case = get_person_case_from_occurrence(episode_case.domain, occurrence_case)
        return json.dumps(get_patient_payload(person_case, occurrence_case, episode_case).to_json())

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


class UpdatePatientPayloadGenerator(NinetyNineDotsBasePayloadGenerator):
    deprecated_format_names = ('case_json',)

    def _get_cases(self, episode_or_person):
        if episode_or_person.type == CASE_TYPE_PERSON:
            person_case = episode_or_person
            episode_case = get_open_episode_case_from_person(person_case.domain, person_case.case_id)
            occurrence_case = get_occurrence_case_from_episode(episode_case.domain, episode_case.case_id)
        elif episode_or_person.type == CASE_TYPE_EPISODE:
            episode_case = episode_or_person
            occurrence_case = get_occurrence_case_from_episode(episode_case.domain, episode_case.case_id)
            person_case = get_person_case_from_occurrence(episode_case.domain, occurrence_case.case_id)
        else:
            raise ENikshayCaseNotFound("wrong case passed to repeater")
        return person_case, occurrence_case, episode_case

    def get_payload(self, repeat_record, episode_or_person):
        person_case, occurrence_case, episode_case = self._get_cases(episode_or_person)
        return json.dumps(get_patient_payload(person_case, occurrence_case, episode_case).to_json())

    def handle_success(self, response, episode_or_person, repeat_record):
        try:
            person_case, occurrence_case, episode_case = self._get_cases(episode_or_person)
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
            person_case, occurrence_case, episode_case = self._get_cases(episode_or_person)
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


class AdherencePayloadGenerator(NinetyNineDotsBasePayloadGenerator):
    deprecated_format_names = ('case_json',)

    def get_payload(self, repeat_record, adherence_case):
        domain = adherence_case.domain
        person_case = get_person_case(domain, adherence_case.case_id)
        adherence_case_properties = adherence_case.dynamic_case_properties()
        date = parse_date(adherence_case.dynamic_case_properties().get('adherence_date'))
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


class TreatmentOutcomePayloadGenerator(NinetyNineDotsBasePayloadGenerator):
    deprecated_format_names = ('case_json',)

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


class UnenrollPatientPayloadGenerator(NinetyNineDotsBasePayloadGenerator):
    deprecated_format_names = ('case_json',)

    def get_payload(self, repeat_record, episode_case):
        domain = episode_case.domain
        person_case = get_person_case_from_occurrence(
            domain, get_occurrence_case_from_episode(
                domain, episode_case.case_id
            ).case_id
        )

        if episode_case.closed:
            reason = episode_case.get_case_property('close_reason')
        elif episode_case.get_case_property('dots_99_enabled') == 'false':
            reason = 'source_changed'
        else:
            reason = 'unknown'

        payload = {
            'beneficiary_id': person_case.case_id,
            'reason': reason,
        }
        return json.dumps(payload)

    def handle_success(self, response, episode_case, repeat_record):
        if response.status_code == 200:
            update_case(
                episode_case.domain,
                episode_case.case_id,
                {
                    "dots_99_registered": "false",
                    "dots_99_error": ""
                }
            )

    def handle_failure(self, response, episode_case, repeat_record):
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
