from collections import namedtuple
from casexml.apps.case.xform import extract_case_blocks
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors


Should = namedtuple('Should', 'method', 'url', 'parser')


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
        return self.requests.get(self._url(uri), *args,
                                 auth=(self.username, self.password), **kwargs)

    def post(self, uri, *args, **kwargs):
        return self.requests.get(self._url(uri), *args,
                                 auth=(self.username, self.password), **kwargs)


def url(url_format_string, **kwargs):
    return url_format_string.format(**kwargs)


def get_how_to_create_person_attribute(person_uuid, attribute_uuid, value):
    # todo: not tested against real openmrs instance
    return Should('POST', url('/person/{person_uuid}/attribute', person_uuid=person_uuid), {
        'uuid': attribute_uuid,
        'value': value,
    })


def get_how_to_update_person_attribute(person_uuid, attribute_uuid, value):
    # todo: not tested against real openmrs instance
    return Should(
        'POST',
        url('/person/{person_uuid}/attribute/{attribute_uuid}',
            person_uuid=person_uuid, attribute_uuid=attribute_uuid),
        {
            'value': value,
        }
    )


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
                extra_fields={field: getattr(case, field, None) for field in extra_fields}
            ))
    return result
