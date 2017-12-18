from __future__ import absolute_import
import json
import pytz

from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.utils.dateparse import parse_datetime

from corehq import toggles
from corehq.apps.domain.decorators import api_auth, check_domain_migration
from dimagi.utils.web import json_response
from dimagi.utils.logging import notify_exception

from corehq.motech.repeaters.views import AddCaseRepeaterView
from custom.enikshay.case_utils import get_adherence_cases_from_episode
from custom.enikshay.integrations.ninetyninedots.exceptions import AdherenceException
from custom.enikshay.integrations.ninetyninedots.utils import (
    AdherenceCaseFactory,
    update_adherence_confidence_level,
    update_default_confidence_level,
)
import six

from custom.enikshay.tasks import get_relevent_case
from custom.enikshay.utils import (
    update_ledger_for_adherence,
    get_adherence_cases_by_date,
)


class RegisterPatientRepeaterView(AddCaseRepeaterView):
    urlname = 'register_99dots_patient'
    page_title = "Register 99DOTS Patients"
    page_name = "Register 99DOTS Patients"


class UpdatePatientRepeaterView(AddCaseRepeaterView):
    urlname = 'update_99dots_patient'
    page_title = "Update 99DOTS Patients"
    page_name = "Update 99DOTS Patients"


class UpdateAdherenceRepeaterView(AddCaseRepeaterView):
    urlname = 'update_99dots_adherence'
    page_title = "Update 99DOTS Adherence"
    page_name = "Update 99DOTS Adherence"


class UpdateTreatmentOutcomeRepeaterView(AddCaseRepeaterView):
    urlname = 'update_99dots_treatment_outcome'
    page_title = "Update 99DOTS Treatment Outcome"
    page_name = "Update 99DOTS Treatment Outcome"


@toggles.NINETYNINE_DOTS.required_decorator()
@api_auth
@require_POST
@csrf_exempt
@check_domain_migration
def update_patient_adherence(request, domain):
    try:
        request_json = json.loads(request.body)
    except ValueError:
        return json_response({"error": "Malformed JSON"}, status_code=400)

    beneficiary_id = request_json.get('beneficiary_id')
    adherence_values = request_json.get('adherences')
    factory = AdherenceCaseFactory(domain, beneficiary_id)

    try:
        validate_beneficiary_id(beneficiary_id)
        validate_adherence_values(adherence_values)
        factory.create_adherence_cases(adherence_values)
    except AdherenceException as e:
        return json_response({"error": six.text_type(e)}, status_code=400)

    try:
        factory.update_episode_adherence_properties()
    except AdherenceException as e:
        notify_exception(
            request,
            message=("An error occurred updating the episode case after receiving a 99DOTS"
                     "adherence case for beneficiary {}. {}").format(beneficiary_id, e))

    try:
        update_ledger_for_episode(domain, factory._episode_case)
    except Exception as e:
        notify_exception(
            request,
            message=("An error occurred updating the ledgers after receiving a 99DOTS"
                     "adherence case for beneficiary {}. {}").format(beneficiary_id, e))
    return json_response({"success": "Patient adherences updated."})


def update_ledger_for_episode(domain, episode_case):
    # refetch all adherence cases to consider all adherence cases post update
    adherence_cases_for_episode = get_adherence_cases_from_episode(domain, episode_case.case_id)
    _cases = [case.to_json() for case in adherence_cases_for_episode]
    adherence_cases_by_date = get_adherence_cases_by_date(_cases)
    for day, cases in six.iteritems(adherence_cases_by_date):
        adherence_case = get_relevent_case(cases)
        if adherence_case and adherence_case['adherence_date']:
            update_ledger_for_adherence(episode_case,
                                        adherence_case['adherence_date'],
                                        adherence_case['adherence_source'],
                                        adherence_case['adherence_value'],
                                        )


@toggles.NINETYNINE_DOTS.required_decorator()
@api_auth
@require_POST
@csrf_exempt
@check_domain_migration
def update_adherence_confidence(request, domain):
    try:
        request_json = json.loads(request.body)
    except ValueError:
        return json_response({"error": "Malformed JSON"}, status_code=400)
    beneficiary_id = request_json.get('beneficiary_id')
    start_date = request_json.get('start_date')
    end_date = request_json.get('end_date')
    confidence_level = request_json.get('confidence_level')

    try:
        validate_beneficiary_id(beneficiary_id)
        validate_dates(start_date, end_date)
        validate_confidence_level(confidence_level)
        update_adherence_confidence_level(
            domain=domain,
            person_id=beneficiary_id,
            start_date=parse_datetime(start_date),
            end_date=parse_datetime(end_date),
            new_confidence=confidence_level
        )
    except AdherenceException as e:
        return json_response({"error": e.message}, status_code=400)

    return json_response({"success": "Patient adherences updated."})


@toggles.NINETYNINE_DOTS.required_decorator()
@api_auth
@require_POST
@csrf_exempt
@check_domain_migration
def update_default_confidence(request, domain):
    try:
        request_json = json.loads(request.body)
    except ValueError:
        return json_response({"error": "Malformed JSON"}, status_code=400)

    beneficiary_id = request_json.get('beneficiary_id')
    confidence_level = request_json.get('confidence_level')

    try:
        validate_beneficiary_id(beneficiary_id)
        validate_confidence_level(confidence_level)
        update_default_confidence_level(domain, beneficiary_id, confidence_level)
    except AdherenceException as e:
        return json_response({"error": e.message}, status_code=400)

    return json_response({"success": "Default Confidence Updated"})


def validate_beneficiary_id(beneficiary_id):
    if beneficiary_id is None:
        raise AdherenceException("Beneficiary ID is null")
    if not isinstance(beneficiary_id, six.string_types):
        raise AdherenceException("Beneficiary ID should be a string")


def validate_dates(start_date, end_date):
    if start_date is None:
        raise AdherenceException("start_date is null")
    if end_date is None:
        raise AdherenceException("end_date is null")
    try:
        parse_datetime(start_date).astimezone(pytz.UTC)
        parse_datetime(end_date).astimezone(pytz.UTC)
    except:
        raise AdherenceException("Malformed Date")


def validate_adherence_values(adherence_values):
    if adherence_values is None or not isinstance(adherence_values, list):
        raise AdherenceException("Adherences invalid")


def validate_confidence_level(confidence_level):
    valid_confidence_levels = ['low', 'medium', 'high']
    if confidence_level not in valid_confidence_levels:
        raise AdherenceException(
            message="New confidence level invalid. Should be one of {}".format(
                valid_confidence_levels
            )
        )
