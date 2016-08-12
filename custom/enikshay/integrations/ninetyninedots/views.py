import json
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.utils.dateparse import parse_datetime

from corehq import toggles
from corehq.apps.domain.decorators import login_or_digest_or_basic_or_apikey
from dimagi.utils.web import json_response

from custom.enikshay.integrations.ninetyninedots.exceptions import AdherenceException
from custom.enikshay.integrations.ninetyninedots.utils import (
    create_adherence_cases,
    update_adherence_confidence_level,
)


@toggles.ENIKSHAY_INTEGRATIONS.required_decorator()
@login_or_digest_or_basic_or_apikey()
@require_POST
@csrf_exempt
def update_patient_adherence(request, domain):
    request_json = json.loads(request.body)
    beneficiary_id = request_json.get('beneficiary_id')
    adherence_values = request_json.get('adherences')

    try:
        validate_beneficiary_id(beneficiary_id)
        validate_adherence_values(adherence_values)
        create_adherence_cases(domain, beneficiary_id, adherence_values, adherence_source="99DOTS")
    except AdherenceException as e:
        return json_response({"error": e.message}, status_code=400)

    return json_response({"success": "Patient adherences updated."})


@toggles.ENIKSHAY_INTEGRATIONS.required_decorator()
@login_or_digest_or_basic_or_apikey()
@require_POST
@csrf_exempt
def update_adherence_confidence(request, domain):
    request_json = json.loads(request.body)
    beneficiary_id = request_json.get('beneficiary_id')
    start_date = request_json.get('start_date')
    end_date = request_json.get('end_date')
    confidence_level = request_json.get('confidence_level')

    try:
        validate_beneficiary_id(beneficiary_id)
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


def validate_beneficiary_id(beneficiary_id):
    if beneficiary_id is None:
        raise AdherenceException(message="Beneficiary ID is null")
    if not isinstance(beneficiary_id, basestring):
        raise AdherenceException(message="Beneficiary ID should be a string")


def validate_adherence_values(adherence_values):
    if adherence_values is None or not isinstance(adherence_values, list):
        raise AdherenceException(message="Adherences invalid")
