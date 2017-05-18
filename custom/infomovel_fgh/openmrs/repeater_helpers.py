from collections import namedtuple


Should = namedtuple('ShouldPostJson', 'method', 'url', 'parser')


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


def get_how_to_search_patients(search_string):
    return Should('GET', url('/patient?q={q}&v=full', id=search_string), None)


class PatientSearchParser(object):
    def __init__(self, response_json):
        self.response_json = response_json

    def get_patient_matching_identifiers(self, patient_identifier_type, patient_identifier):
        patient, = [
            patient
            for patient in self.response_json['results']
            for identifier in patient['identifiers']
            if identifier['identifier'] == patient_identifier
            and identifier['identifierType']['uuid'] == patient_identifier_type
        ]
        return patient
