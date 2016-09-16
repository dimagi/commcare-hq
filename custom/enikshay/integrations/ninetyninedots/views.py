import json
import pytz
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.utils.dateparse import parse_datetime

from corehq import toggles
from corehq.apps.domain.decorators import login_or_digest_or_basic_or_apikey
from dimagi.utils.web import json_response

from corehq.apps.repeaters.views import AddCaseRepeaterView
from custom.enikshay.integrations.ninetyninedots.exceptions import AdherenceException
from custom.enikshay.integrations.ninetyninedots.utils import (
    create_adherence_cases,
    update_adherence_confidence_level,
    update_default_confidence_level,
)


class RegisterPatientRepeaterView(AddCaseRepeaterView):
    urlname = 'register_99dots_patient'
    page_title = "Register 99DOTS Patients"
    page_name = "Register 99DOTS Patients"


class UpdatePatientRepeaterView(AddCaseRepeaterView):
    urlname = 'update_99dots_patient'
    page_title = "Update 99DOTS Patients"
    page_name = "Update 99DOTS Patients"


@toggles.NINETYNINE_DOTS.required_decorator()
@login_or_digest_or_basic_or_apikey()
@require_POST
@csrf_exempt
def update_patient_adherence(request, domain):
    try:
        request_json = json.loads(request.body)
    except ValueError:
        return json_response({"error": "Malformed JSON"}, status_code=400)

    beneficiary_id = request_json.get('beneficiary_id')
    adherence_values = request_json.get('adherences')

    try:
        validate_beneficiary_id(beneficiary_id)
        validate_adherence_values(adherence_values)
        create_adherence_cases(domain, beneficiary_id, adherence_values)
    except AdherenceException as e:
        return json_response({"error": e.message}, status_code=400)

    return json_response({"success": "Patient adherences updated."})


@toggles.NINETYNINE_DOTS.required_decorator()
@login_or_digest_or_basic_or_apikey()
@require_POST
@csrf_exempt
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
@login_or_digest_or_basic_or_apikey()
@require_POST
@csrf_exempt
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
    if not isinstance(beneficiary_id, basestring):
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
