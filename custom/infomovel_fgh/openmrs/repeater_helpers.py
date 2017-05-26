from collections import namedtuple
from casexml.apps.case.xform import extract_case_blocks
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors


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
            if identifier['identifier'] == patient_identifier and
            identifier['identifierType']['uuid'] == patient_identifier_type
        ]
        return patient


def filter_case_blocks_by_case_type(domain, case_blocks, case_types):
    yes = []
    maybe = {}

    for case_block in case_blocks:
        if 'create' in case_block and case_block['create'].get('case_type') in case_types:
            yes.append(case_block)
        elif 'create' not in case_block:
            maybe[case_block['@case_id']] = case_block

    yes_case_ids = [case.case_id for case in CaseAccessors(domain).get_cases(maybe.keys())
                    if case.type in case_types]
    for case_id in yes_case_ids:
        yes.append(maybe[case_id])

    return yes


def get_relevant_case_updates_from_form_json(domain, form_json, case_types):
    """
    return type is {case_id => {property => value}}
    """
    case_blocks = extract_case_blocks(form_json)
    case_blocks = filter_case_blocks_by_case_type(domain, case_blocks, case_types)
    return {
        case_block['@case_id']: dict(
            case_block.get('create', {}).items() +
            case_block.get('update', {}).items()
        )
        for case_block in case_blocks
    }
