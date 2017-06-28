from collections import namedtuple
from requests import HTTPError
from casexml.apps.case.xform import extract_case_blocks
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors


Should = namedtuple('Should', ['method', 'url', 'parser'])


class Requests(object):
    def __init__(self, base_url, username, password):
        import requests
        self.requests = requests
        self.base_url = base_url
        self.username = username
        self.password = password

    def _url(self, uri):
        return '{}{}'.format(self.base_url, uri)

    def get(self, uri, *args, **kwargs):
        # print 'GET', self._url(uri), args, kwargs
        return self.requests.get(self._url(uri), *args,
                                 auth=(self.username, self.password), **kwargs)

    def post(self, uri, *args, **kwargs):
        # print 'POST', self._url(uri), args, kwargs
        return self.requests.post(self._url(uri), *args,
                                  auth=(self.username, self.password), **kwargs)


def url(url_format_string, **kwargs):
    return url_format_string.format(**kwargs)


def create_patient_and_person(requests):
    response = requests.post('/ws/rest/v1/person', json={
        'gender': 'M',
        'names': [{
            "givenName": "Daniel",
            "middleName": "Mattos",
            "familyName": "Roberts",
            "preferred": True,
        }],
        'addresses': [{
            'address1': "1350 Road Rd",
            'postalCode': '12345',
            'preferred': True,
        }],
    })

    try:
        response.raise_for_status()
    except HTTPError:
        print response.json()
        raise

    person_uuid = response.json()['uuid']
    print person_uuid

    response = requests.post('/ws/rest/v1/patient', json={
        'uuid': person_uuid,
        'person': person_uuid,
        'identifiers': [{
            'identifierType': "05a29f94-c0ed-11e2-94be-8c13b969e334",
            "identifier": "99999K",
            "location": "58c57d25-8d39-41ab-8422-108a0c277d98",
        }],
    })
    try:
        response.raise_for_status()
    except HTTPError:
        print response.json()
        raise
    print response.json()


def create_person_attribute(requests, person_uuid, attribute_type_uuid, value):
    # todo: not tested against real openmrs instance
    return requests.post('/ws/rest/v1/person/{person_uuid}/attribute'.format(
        person_uuid=person_uuid), json={
            'attributeType': attribute_type_uuid,
            'value': value,
        },
    ).json()


def update_person_attribute(requests, person_uuid, attribute_uuid, attribute_type_uuid, value):
    return requests.post('/ws/rest/v1/person/{person_uuid}/attribute/{attribute_uuid}'.format(
        person_uuid=person_uuid, attribute_uuid=attribute_uuid), json={
            'value': value,
            'attributeType': attribute_type_uuid,
        }
    ).json()


def set_person_properties(requests, person_uuid, properties):
    allowed_properties = (
        'gender', 'birthdate', 'birthdateEstimated', 'dead', 'deathDate', 'causeOfDeath')
    for p in properties:
        assert p in allowed_properties

    response = requests.post('/ws/rest/v1/person/{person_uuid}'.format(
        person_uuid=person_uuid), json=properties
    )
    try:
        response.raise_for_status()
    except HTTPError:
        print response.json()
        raise
    return response.json()


def server_datetime_to_openmrs_timestamp(dt):
    openmrs_timestamp = dt.isoformat()[:-3] + '+0000'
    # todo: replace this with tests
    assert len(openmrs_timestamp) == len('2017-06-27T09:36:47.000-0400'), openmrs_timestamp
    return openmrs_timestamp


def create_visit(requests, person_uuid, visit_datetime, values_for_concept, encounter_type,
                 openmrs_form, visit_type, patient_uuid=None):
    timestamp = server_datetime_to_openmrs_timestamp(visit_datetime)
    patient_uuid = patient_uuid or person_uuid
    observations = [
        {
            "concept": concept_uuid,
            "value": value,
            "person": person_uuid,
            "obsDatetime": timestamp,
        }
        for concept_uuid, values in values_for_concept.items()
        for value in values
    ]
    observation_uuids = []
    for observation in observations:
        response = requests.post('/ws/rest/v1/obs', json=observation)
        try:
            response.raise_for_status()
        except HTTPError:
            print response.json()
            raise
        observation_uuids.append(response.json()['uuid'])

    print 'observations', observation_uuids
    encounters = [
        {
            "encounterType": encounter_type,
            "form": openmrs_form,
            "obs": observation_uuids,
            "patient": patient_uuid,
        }
    ]
    encounter_uuids = []
    for encounter in encounters:
        response = requests.post('/ws/rest/v1/encounter', json=encounter)

        try:
            response.raise_for_status()
        except HTTPError:
            print response.json()
            raise
        encounter_uuids.append(response.json()['uuid'])

    print 'encounters', encounter_uuids

    visit = {
        "encounters": encounter_uuids,
        "patient": patient_uuid,
        "visitType": visit_type,
    }

    response = requests.post('/ws/rest/v1/visit', json=visit)
    try:
        response.raise_for_status()
    except HTTPError:
        print response.json()
        raise
    print response.json()['uuid']


def search_patients(requests, search_string):
    return requests.get('/ws/rest/v1/patient', {'q': search_string, 'v': 'full'}).json()


def get_patient_by_id(requests, patient_identifier_type, patient_identifier):
    response_json = search_patients(requests, patient_identifier)
    return PatientSearchParser(response_json).get_patient_matching_identifiers(
        patient_identifier_type, patient_identifier)


class PatientSearchParser(object):
    def __init__(self, response_json):
        self.response_json = response_json

    def get_patient_matching_identifiers(self, patient_identifier_type, patient_identifier):
        patients = [
            patient
            for patient in self.response_json['results']
            for identifier in patient['identifiers']
            if identifier['identifier'] == patient_identifier and
            identifier['identifierType']['uuid'] == patient_identifier_type
        ]
        try:
            patient, = patients
        except ValueError:
            return None
        else:
            return patient


CaseTriggerInfo = namedtuple('CaseTriggerInfo',
                             ['case_id', 'updates', 'created', 'closed', 'extra_fields'])


def get_relevant_case_updates_from_form_json(domain, form_json, case_types, extra_fields):
    result = []
    case_blocks = extract_case_blocks(form_json)
    cases = CaseAccessors(domain).get_cases(
        [case_block['@case_id'] for case_block in case_blocks], ordered=True)
    for case, case_block in zip(cases, case_blocks):
        assert case_block['@case_id'] == case.case_id
        if case.type in case_types:
            result.append(CaseTriggerInfo(
                case_id=case_block['@case_id'],
                updates=dict(
                    case_block.get('create', {}).items() +
                    case_block.get('update', {}).items()
                ),
                created='create' in case_block,
                closed='close' in case_block,
                extra_fields={field: case.get_case_property(field) for field in extra_fields}
            ))
    return result


def get_patient_identifier_types(requests):
    return requests.get('/ws/rest/v1/patientidentifiertype').json()


def get_person_attribute_types(requests):
    return requests.get('/ws/rest/v1/personattributetype').json()
