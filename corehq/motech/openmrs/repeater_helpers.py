from __future__ import absolute_import

from __future__ import unicode_literals
from collections import namedtuple
from datetime import timedelta
import re

from requests import HTTPError
from six.moves import zip

from casexml.apps.case.xform import extract_case_blocks
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.motech.openmrs.logger import logger
from corehq.motech.openmrs.openmrs_config import IdMatcher
from corehq.motech.utils import pformat_json


Should = namedtuple('Should', ['method', 'url', 'parser'])
PERSON_PROPERTIES = (
    'gender',
    'age',
    'birthdate',
    'birthdateEstimated',
    'dead',
    'deathDate',
    'deathdateEstimated',
    'causeOfDeath',
)
PERSON_SUBRESOURCES = ('attribute', 'address', 'name')
NAME_PROPERTIES = (
    'givenName',
    'familyName',
    'middleName',
    'familyName2',
    'prefix',
    'familyNamePrefix',
    'familyNameSuffix',
    'degree',
)
ADDRESS_PROPERTIES = (
    'address1',
    'address2',
    'cityVillage',
    'stateProvince',
    'country',
    'postalCode',
    'latitude',
    'longitude',
    'countyDistrict',
    'address3',
    'address4',
    'address5',
    'address6',
    'startDate',
    'endDate',
)
# To match cases against their OpenMRS Person UUID, set the IdMatcher's identifier_type_id to the value of
# PERSON_UUID_IDENTIFIER_TYPE_ID. To match against any other OpenMRS identifier, set the IdMatcher's
# identifier_type_id to the UUID of the OpenMRS Identifier Type.
PERSON_UUID_IDENTIFIER_TYPE_ID = 'uuid'


class Requests(object):
    def __init__(self, base_url, username, password):
        import requests
        self.requests = requests
        self.base_url = base_url
        self.username = username
        self.password = password

    def get_url(self, uri):
        return '/'.join((self.base_url.rstrip('/'), uri.lstrip('/')))

    def get(self, uri, *args, **kwargs):
        return self.requests.get(self.get_url(uri), *args,
                                 auth=(self.username, self.password), **kwargs)

    def post(self, uri, *args, **kwargs):
        return self.requests.post(self.get_url(uri), *args,
                                  auth=(self.username, self.password), **kwargs)

    def post_with_raise(self, uri, *args, **kwargs):
        response = self.post(uri, *args, **kwargs)
        try:
            response.raise_for_status()
        except HTTPError as err:
            err_request, err_response = parse_request_exception(err)
            logger.error('Request: ', err_request)
            logger.error('Response: ', err_response)
            raise
        return response


def parse_request_exception(err):
    """
    Parses an instance of RequestException and returns a request
    string and response string tuple
    """
    err_request = '{method} {url}\n\n{body}'.format(
        method=err.request.method,
        url=err.request.url,
        body=err.request.body
    ) if err.request.body else ' '.join((err.request.method, err.request.url))
    err_content = pformat_json(err.response.content)  # pformat_json returns non-JSON values unchanged
    err_response = '\n\n'.join((str(err), err_content))
    return err_request, err_response


def url(url_format_string, **kwargs):
    return url_format_string.format(**kwargs)


def create_person_attribute(requests, person_uuid, attribute_type_uuid, value):
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


def server_datetime_to_openmrs_timestamp(dt):
    openmrs_timestamp = dt.isoformat()[:-3] + '+0000'
    # todo: replace this with tests
    assert len(openmrs_timestamp) == len('2017-06-27T09:36:47.000-0400'), openmrs_timestamp
    return openmrs_timestamp


def create_visit(requests, person_uuid, provider_uuid, visit_datetime, values_for_concept, encounter_type,
                 openmrs_form, visit_type, location_uuid=None, patient_uuid=None):
    patient_uuid = patient_uuid or person_uuid
    start_datetime = server_datetime_to_openmrs_timestamp(visit_datetime)
    stop_datetime = server_datetime_to_openmrs_timestamp(
        visit_datetime + timedelta(days=1) - timedelta(seconds=1)
    )

    visit = {
        'patient': patient_uuid,
        'visitType': visit_type,
        'startDatetime': start_datetime,
        'stopDatetime': stop_datetime,
    }
    if location_uuid:
        visit['location'] = location_uuid
    response = requests.post_with_raise('/ws/rest/v1/visit', json=visit)
    visit_uuid = response.json()['uuid']

    encounter = {
        'encounterDatetime': start_datetime,
        'patient': patient_uuid,
        'form': openmrs_form,
        'encounterType': encounter_type,
        'visit': visit_uuid,
    }
    if location_uuid:
        encounter['location'] = location_uuid
    response = requests.post_with_raise('/ws/rest/v1/encounter', json=encounter)
    encounter_uuid = response.json()['uuid']
    if provider_uuid:
        encounter_provider = {'provider': provider_uuid}
        uri = '/ws/rest/v1/encounter/{uuid}/encounterprovider'.format(uuid=encounter_uuid)
        requests.post_with_raise(uri, json=encounter_provider)

    observation_uuids = []
    for concept_uuid, values in values_for_concept.items():
        for value in values:
            observation = {
                'concept': concept_uuid,
                'person': person_uuid,
                'obsDatetime': start_datetime,
                'encounter': encounter_uuid,
                'value': value,
            }
            if location_uuid:
                observation['location'] = location_uuid
            response = requests.post_with_raise('/ws/rest/v1/obs', json=observation)
            observation_uuids.append(response.json()['uuid'])

    logger.debug('Observations created: ', observation_uuids)


def search_patients(requests, search_string):
    try:
        # Finding the patient is the first request sent to the server. If there is a mistake in the server details,
        # or the server is offline, this is where we will discover it.
        response = requests.get('/ws/rest/v1/patient', {'q': search_string, 'v': 'full'})
        response.raise_for_status()
    except HTTPError as err:
        # raise_for_status() raised an HTTPError.
        err_request, err_response = parse_request_exception(err)
        logger.error('Error encountered searching patients')
        logger.error('Request: ', err_request)
        logger.error('Response: ', err_response)
        http_error_msg = (
            'An error was when encountered searching patients: {}. Check in Data Forwarding that the server URL '
            'includes the path to the API, and that the password is correct'.format(err)
        )  # This message will be shown in the Repeat Records report, and needs to be useful to an administrator
        raise HTTPError(http_error_msg, response=err.response)
    except Exception as err:
        # get() failed -- probably a connection failure.
        logger.error('Error encountered searching patients: ', str(err))
        raise err.__class__(
            'Unable to send request to OpenMRS server: {}. Please check the server address in Data Forwarding and '
            'that the server is online.'.format(err)
        )

    return response.json()


def get_patient_by_uuid(requests, uuid):
    if not uuid:
        return None
    if not re.match(r'^[a-fA-F0-9\-]{36}$', uuid):
        logger.debug('Person UUID "{}" failed validation'.format(uuid))
        return None
    return requests.get('/ws/rest/v1/patient/' + uuid, {'v': 'full'}).json()


def get_patient_by_id(requests, patient_identifier_type, patient_identifier):
    if patient_identifier_type == PERSON_UUID_IDENTIFIER_TYPE_ID:
        patient = get_patient_by_uuid(requests, patient_identifier)
        return patient
    else:
        response_json = search_patients(requests, patient_identifier)
        return PatientSearchParser(response_json).get_patient_matching_identifiers(
            patient_identifier_type, patient_identifier)


def update_person_name(requests, info, openmrs_config, person_uuid, name_uuid):
    properties = {
        property_: value_source.get_value(info)
        for property_, value_source in openmrs_config.case_config.person_preferred_name.items()
        if property_ in NAME_PROPERTIES and value_source.get_value(info)
    }
    if properties:
        requests.post_with_raise(
            '/ws/rest/v1/person/{person_uuid}/name/{name_uuid}'.format(
                person_uuid=person_uuid,
                name_uuid=name_uuid,
            ),
            json=properties,
        )


def create_person_address(requests, info, openmrs_config, person_uuid):
    properties = {
        property_: value_source.get_value(info)
        for property_, value_source in openmrs_config.case_config.person_preferred_address.items()
        if property_ in ADDRESS_PROPERTIES and value_source.get_value(info)
    }
    if properties:
        requests.post_with_raise(
            '/ws/rest/v1/person/{person_uuid}/address/'.format(person_uuid=person_uuid),
            json=properties,
        )


def update_person_address(requests, info, openmrs_config, person_uuid, address_uuid):
    properties = {
        property_: value_source.get_value(info)
        for property_, value_source in openmrs_config.case_config.person_preferred_address.items()
        if property_ in ADDRESS_PROPERTIES and value_source.get_value(info)
    }
    if properties:
        requests.post_with_raise(
            '/ws/rest/v1/person/{person_uuid}/address/{address_uuid}'.format(
                person_uuid=person_uuid,
                address_uuid=address_uuid,
            ),
            json=properties,
        )


def get_subresource_instances(requests, person_uuid, subresource):
    assert subresource in PERSON_SUBRESOURCES
    return requests.get('/ws/rest/v1/person/{person_uuid}/{subresource}'.format(
        person_uuid=person_uuid,
        subresource=subresource,
    )).json()['results']


def get_patient(requests, info, openmrs_config, problem_log):
    patient = None
    for id_matcher in openmrs_config.case_config.id_matchers:
        assert isinstance(id_matcher, IdMatcher)
        if id_matcher.case_property in info.extra_fields:
            patient = get_patient_by_id(
                requests, id_matcher.identifier_type_id,
                info.extra_fields[id_matcher.case_property])
            if patient:
                break

    if not patient:
        problem_log.append("Could not find patient matching case")
        return

    return patient


def update_person_properties(requests, info, openmrs_config, person_uuid):
    properties = {
        property_: value_source.get_value(info)
        for property_, value_source in openmrs_config.case_config.person_properties.items()
        if property_ in PERSON_PROPERTIES and value_source.get_value(info)
    }
    if properties:
        for p in properties:
            assert p in PERSON_PROPERTIES
        requests.post_with_raise(
            '/ws/rest/v1/person/{person_uuid}'.format(person_uuid=person_uuid),
            json=properties
        )


def sync_person_attributes(requests, info, openmrs_config, person_uuid, attributes):
    existing_person_attributes = {
        attribute['attributeType']['uuid']: (attribute['uuid'], attribute['value'])
        for attribute in attributes
    }
    for person_attribute_type, value_source in openmrs_config.case_config.person_attributes.items():
        value = value_source.get_value(info)
        if person_attribute_type in existing_person_attributes:
            attribute_uuid, existing_value = existing_person_attributes[person_attribute_type]
            if value != existing_value:
                update_person_attribute(requests, person_uuid, attribute_uuid, person_attribute_type, value)
        else:
            create_person_attribute(requests, person_uuid, person_attribute_type, value)


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
                             ['case_id', 'updates', 'created', 'closed', 'extra_fields', 'form_question_values'])


def get_form_question_values(form_json):
    """
    Returns question-value pairs to result where questions are given as "/data/foo/bar"

    >>> get_form_question_values({'form': {'foo': {'bar': 'baz'}}})
    {'/data/foo/bar': 'baz'}

    """
    _reserved_keys = ('@uiVersion', '@xmlns', '@name', '#type', 'case', 'meta', '@version')

    def _recurse_form_questions(form_dict, path, result_):
        for key, value in form_dict.items():
            if key in _reserved_keys:
                continue
            new_path = path + [key]
            if isinstance(value, list):
                # Repeat group
                for v in value:
                    assert isinstance(v, dict)
                    _recurse_form_questions(v, new_path, result_)
            elif isinstance(value, dict):
                # Group
                _recurse_form_questions(value, new_path, result_)
            else:
                # key is a question and value is its answer
                question = '/'.join(new_path)
                result_[question] = value

    result = {}
    _recurse_form_questions(form_json['form'], ['/data'], result)  # "/data" is just convention, hopefully familiar
    # from form builder. The form's data will usually be immediately under "form_json['form']" but not necessarily.
    # If this causes problems we may need a more reliable way to get to it.
    return result


def get_relevant_case_updates_from_form_json(domain, form_json, case_types, extra_fields):
    result = []
    case_blocks = extract_case_blocks(form_json)
    cases = CaseAccessors(domain).get_cases(
        [case_block['@case_id'] for case_block in case_blocks], ordered=True)
    for case, case_block in zip(cases, case_blocks):
        assert case_block['@case_id'] == case.case_id
        if not case_types or case.type in case_types:
            result.append(CaseTriggerInfo(
                case_id=case_block['@case_id'],
                updates=dict(
                    list(case_block.get('create', {}).items()) +
                    list(case_block.get('update', {}).items())
                ),
                created='create' in case_block,
                closed='close' in case_block,
                extra_fields={field: case.get_case_property(field) for field in extra_fields},
                form_question_values={}
            ))
    return result


def get_patient_identifier_types(requests):
    return requests.get('/ws/rest/v1/patientidentifiertype').json()


def get_person_attribute_types(requests):
    return requests.get('/ws/rest/v1/personattributetype').json()
