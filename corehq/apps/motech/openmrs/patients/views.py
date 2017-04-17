import json
from django.http import HttpResponse
from corehq.apps.motech.connected_accounts import get_openmrs_requests_object
from corehq.apps.motech.openmrs.patients.patientidentifiertypes import \
    openmrs_patient_identifier_type_json_from_api_json
from corehq.apps.motech.openmrs.restclient.listapi import OpenmrsListApi
from corehq.apps.motech.permissions import require_motech_permissions


@require_motech_permissions
def search_patients(request, domain):
    patient_identifier_type = request.GET.get('idtype')
    patient_id = request.GET.get('id')
    if not patient_id or not patient_identifier_type:
        return HttpResponse(json.dumps({
            'badrequest': 'Must include params idtype and id'
        }), status=400)
    requests = get_openmrs_requests_object(domain)
    patients = requests.get('/openmrs/ws/rest/v1/patient', params={'q': patient_id, 'v': 'full'}).json()['results']
    patients = [
        patient for patient in patients
        if any(
            identifier['identifier'] == patient_id
            and identifier['identifierType']['uuid'] == patient_identifier_type
            for identifier in patient['identifiers']
        )
    ]
    return HttpResponse(
        json.dumps([{
            'uuid': p['uuid'],
            'display': p['display'],
        } for p in patients]), content_type='text/json')


@require_motech_permissions
def all_patient_identifier_types(request, domain):
    requests = get_openmrs_requests_object(domain)
    api = OpenmrsListApi(requests, 'patientidentifiertype')
    patient_identifier_types = [
        openmrs_patient_identifier_type_json_from_api_json(patient_identifier_type).to_json()
        for patient_identifier_type in api.get_all()
    ]
    return HttpResponse(json.dumps(patient_identifier_types), content_type='text/json')
