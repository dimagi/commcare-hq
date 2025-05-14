import requests
import jwt
import pytz
import time
import uuid

from datetime import datetime, timedelta
from django.conf import settings

from jsonpath_ng import parse as parse_jsonpath
from urllib.parse import urlencode

from corehq.apps.hqcase.case_helper import CaseHelper
from corehq.form_processor.models import CommCareCase, CommCareCaseIndex
from corehq.util.timezones.conversions import ServerTime


OAUTH_URL = "https://ws-interconnect-fhir.partners.org/Interconnect-FHIR-MU-PRD/oauth2/token"
PATIENT_URL = "https://ws-interconnect-fhir.partners.org/Interconnect-FHIR-MU-PRD/api/FHIR/R4/Patient"
APPOINTMENT_URL = "https://ws-interconnect-fhir.partners.org/Interconnect-FHIR-MU-PRD/api/FHIR/R4/Appointment"


def handle_response(response):
    if 200 <= response.status_code < 300:
        return response.json()
    response.raise_for_status()


def generate_epic_jwt():
    key = settings.EPIC_PRIVATE_KEY
    # token will expire in 4 mins
    exp = int(time.time()) + 240
    jti = str(uuid.uuid4())
    header = {
        "alg": "RS256",
        "typ": "JWT",
    }
    payload = {
        "iss": settings.EPIC_CLIENT_ID,
        "sub": settings.EPIC_CLIENT_ID,
        "aud": OAUTH_URL,
        "jti": jti,
        "exp": exp
    }
    token = jwt.encode(payload, key, algorithm="RS256", headers=header)
    return token


def request_epic_access_token():
    headers = {
        "Content_Type": "application/x-www-form-urlencoded",
    }
    data = {
        "grant_type": "client_credentials",
        "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
        "client_assertion": generate_epic_jwt()
    }
    url = OAUTH_URL
    response = requests.post(url, data=data, headers=headers)
    response_json = handle_response(response)

    return response_json.get('access_token')


def get_patient_fhir_id(given_name, family_name, birthdate, access_token):
    base_url = PATIENT_URL
    params = {
        'birthdate': birthdate,
        'family': family_name,
        'given': given_name,
        '_format': 'json'
    }
    url = f'{base_url}?{urlencode(params)}'
    headers = {
        'authorization': f'Bearer {access_token}',
    }
    response = requests.get(url, headers=headers)
    response_json = handle_response(response)
    fhir_id = None

    path = parse_jsonpath('entry[0].resource.id')
    matches = path.find(response_json)
    if matches:
        fhir_id = matches[0].value
    return fhir_id


def filter_appointments_by_date(appointments_entries_json, study_start_date, weeks_from_start_date):
    """
    Returns a list of appointment entries
    :param appointments_entries_json: Json response data for Epic appointment search
    :param study_start_date: A date case property formatted YYYY-MM-DD
    :param weeks_from_start_date: Number of weeks after study start to filter by
    :return: A list of json entries
    """
    appointments = []
    study_start_datetime = datetime.strptime(study_start_date, "%Y-%m-%d")
    study_end_datetime = study_start_datetime + timedelta(weeks=weeks_from_start_date)
    for entry in appointments_entries_json:
        entry_start = entry.get("resource", {}).get("start")
        if entry_start:
            local_appointment_date, local_appointment_time = convert_utc_timestamp_to_date_and_time(entry_start)
            local_appointment_datetime = datetime.strptime(local_appointment_date, "%Y-%m-%d")

            if (study_start_datetime <= local_appointment_datetime <= study_end_datetime):
                appointments.append(entry)

    return appointments


def get_epic_appointments_for_patient(fhir_id, access_token, opened_on, study_start_date=None):
    if not fhir_id:
        return []
    appointments = []
    headers = {
        'authorization': f'Bearer {access_token}',
    }
    base_url = APPOINTMENT_URL
    params = {
        'patient': fhir_id,
        'service-category': 'appointment',
        '_format': 'json'
    }
    url = f'{base_url}?{urlencode(params)}'
    response = requests.get(url, headers=headers)
    response_json = handle_response(response)

    entries = response_json['entry']

    if not study_start_date:
        appointments = filter_appointments_by_date(entries, opened_on, 12)
    else:
        appointments = filter_appointments_by_date(entries, study_start_date, 12)

    return appointments


def convert_utc_timestamp_to_date_and_time(utc_timestamp):
    local_zone = pytz.timezone('US/Eastern')
    utc_datetime = datetime.fromisoformat(utc_timestamp.replace('Z', ''))
    utc_datetime = utc_datetime.replace(tzinfo=None)
    local_datetime = ServerTime(utc_datetime).user_time(local_zone).done()
    date = local_datetime.strftime('%Y-%m-%d')
    time = local_datetime.strftime('%H:%M')

    return date, time


def sync_all_appointments_domain(domain):
    try:
        access_token = request_epic_access_token()
    except Exception:
        return None

    def _get_appointment_resource_values(appointment_resource):
        appointment_dict = {}
        description = appointment_resource.get('description') or 'NO DESCRIPTION LISTED'
        appointment_dict.update({"appointment_description": description})
        appointment_dict.update({"appointment_fhir_timestamp": appointment_resource.get('start')})
        appointment_date, appointment_time = convert_utc_timestamp_to_date_and_time(
            appointment_dict.get("appointment_fhir_timestamp"))
        appointment_dict.update({"appointment_date": appointment_date})
        appointment_dict.update({"appointment_time": appointment_time})
        appointment_dict.update({"appointment_fhir_id": appointment_resource.get('id')})
        reason = ''
        practitioner = ''
        for p in appointment_resource.get('participant'):
            actor = p.get('actor')
            if actor and actor.get('reference') is not None and 'Practitioner' in actor.get('reference'):
                practitioner = actor.get('display')
                break
        reason_code = appointment_resource.get('reasonCode')
        if reason_code and reason_code[0] is not None:
            reason = reason_code[0].get('text')
        appointment_dict.update({"reason": reason})
        appointment_dict.update({"practitioner": practitioner})

        return appointment_dict

    # get all patient case ids for domain
    patient_case_ids = CommCareCase.objects.get_open_case_ids_in_domain_by_type(domain, 'patient')
    # get all patient cases
    patient_cases = CommCareCase.objects.get_cases(patient_case_ids)

    # get extension (appointment) cases ids, for all patients
    appointment_case_ids = CommCareCaseIndex.objects.get_extension_case_ids(
        domain, patient_case_ids, False, 'appointment')
    # get appointment cases in commcare
    appointment_cases = CommCareCase.objects.get_cases(appointment_case_ids)

    # map fhir ids to appointments currently in commcare
    appointment_map = {
        appointment_case.get_case_property('fhir_id'): appointment_case for appointment_case in appointment_cases
    }
    for patient in patient_cases:
        patient_helper = CaseHelper(case=patient, domain=domain)
        patient_fhir_id = patient.get_case_property('fhir_id')
        if not patient_fhir_id:
            given = patient.get_case_property('first_name')
            family = patient.get_case_property('last_name')
            birthdate = patient.get_case_property('dob')
            if given and family and birthdate:
                patient_fhir_id = get_patient_fhir_id(given, family, birthdate, access_token)

            if patient_fhir_id is not None:
                patient_helper.update({'properties': {
                    'fhir_id': patient_fhir_id,
                }})
            else:
                continue

        epic_appointments_to_add = []
        epic_appointments_to_update = []
        # Get all appointments for patient from epic
        study_start_date = patient.get_case_property('study_start_date')
        opened_on = patient.get_case_property('opened_on').strftime("%Y-%m-%d")
        epic_appointment_records = get_epic_appointments_for_patient(patient_fhir_id,
                                                                     access_token,
                                                                     opened_on,
                                                                     study_start_date
                                                                     )
        for appointment in epic_appointment_records:
            appointment_resource = appointment.get('resource')
            appointment_id = appointment_resource.get('id')
            if appointment_id and appointment_id not in appointment_map:
                epic_appointments_to_add.append(appointment)
            elif appointment_id:
                epic_appointments_to_update.append(appointment)

        # Add new appointments to commcare
        for appointment in epic_appointments_to_add:
            appointment_create_helper = CaseHelper(domain=domain)
            new_appointment_dict = {}
            appointment_resource = appointment.get('resource')
            if appointment_resource is not None:
                new_appointment_dict = _get_appointment_resource_values(appointment_resource)
            host_case_id = patient.get_case_property('case_id')
            owner_id = patient.get_case_property('owner_id')
            appointment_fhir_timestamp = new_appointment_dict.get("appointment_fhir_timestamp")
            appointment_description = new_appointment_dict.get("appointment_description")
            appointment_case_data = {
                'owner_id': owner_id,
                'case_name': f'[{appointment_fhir_timestamp}]: {appointment_description}',
                'case_type': 'appointment',
                'indices': {
                    'patient': {
                        'case_id': host_case_id,
                        'case_type': 'patient',
                        'relationship': 'extension',
                    }
                },
                'properties': {
                    'appointment_description': appointment_description,
                    'appointment_fhir_timestamp': appointment_fhir_timestamp,
                    'appointment_date': new_appointment_dict.get("appointment_date"),
                    'appointment_time': new_appointment_dict.get("appointment_time"),
                    'patient_fhir_id': patient_fhir_id,
                    'fhir_id': new_appointment_dict.get("appointment_fhir_id"),
                    'reason': new_appointment_dict.get("reason"),
                    'practitioner': new_appointment_dict.get("practitioner")
                }
            }
            appointment_create_helper.create_case(appointment_case_data)

        # Update existing appointments in commcare if properties have changed in epic
        for appointment in epic_appointments_to_update:
            epic_properties_map = {}
            appointment_resource = appointment.get('resource')
            if appointment_resource is not None:
                update_appointment_dict = _get_appointment_resource_values(appointment_resource)

                epic_properties_map.update({
                    'appointment_description': update_appointment_dict.get("appointment_description"),
                    'appointment_fhir_timestamp': update_appointment_dict.get("appointment_fhir_timestamp"),
                    'practitioner': update_appointment_dict.get("practitioner"),
                    'reason': update_appointment_dict.get("reason")
                })
            appointment_case = appointment_map.get(update_appointment_dict.get("appointment_fhir_id"))
            appointment_update_helper = CaseHelper(case=appointment_case, domain=domain)
            case_properties_to_update = {}
            changes = False
            # check for changes and add to case_properties_to_update
            for k, v in epic_properties_map.items():
                current_value = appointment_case.get_case_property(k)
                if current_value != v:
                    if k == 'appointment_fhir_timestamp':
                        # these are quivalent to the minute
                        if v[0:16] == current_value[0:16]:
                            continue
                        else:
                            appointment_date, appointment_time = convert_utc_timestamp_to_date_and_time(v)
                            case_properties_to_update.update({
                                'appointment_date': appointment_date,
                                'appointment_time': appointment_time,
                            })
                    changes = True
                    case_properties_to_update.update({k: v})

            if changes:
                appointment_update_helper.update({'properties': case_properties_to_update})
