from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from corehq import toggles
from corehq.apps.domain.decorators import login_or_digest_or_basic_or_apikey
from dimagi.utils.web import json_response

from custom.enikshay.integrations.ninetyninedots.exceptions import AdherenceException
from custom.enikshay.integrations.ninetyninedots.utils import create_adherence_cases


@toggles.ENIKSHAY_INTEGRATIONS.required_decorator()
@login_or_digest_or_basic_or_apikey()
@require_POST
@csrf_exempt
def update_patient_adherence(request, domain):
    beneficiary_id = request.POST.get('beneficiary_id')
    adherence_values = request.POST.get('adherences')

    try:
        validate_patient_adherence_data(beneficiary_id, adherence_values)
        create_adherence_cases(domain, beneficiary_id, adherence_values, adherence_source="99DOTS")
    except AdherenceException as e:
        return json_response({"error": e.message}, status_code=400)

    return json_response({"success": "Patient adherences updated."})


def validate_patient_adherence_data(beneficiary_id, adherence_values):
    if beneficiary_id is None:
        raise AdherenceException(message="Beneficiary ID is null")

    if adherence_values is None or not isinstance(adherence_values, list):
        raise AdherenceException(message="Adherences invalid")
