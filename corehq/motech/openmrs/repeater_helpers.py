from __future__ import absolute_import

from __future__ import unicode_literals
from collections import namedtuple, defaultdict
from datetime import timedelta
import re

from requests import HTTPError
from six.moves import zip

from casexml.apps.case.xform import extract_case_blocks
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.cases import get_wrapped_owner, get_owner_id
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.motech.openmrs.finders import PatientFinder
from corehq.motech.openmrs.logger import logger
from corehq.motech.openmrs.workflow import WorkflowTask, task
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


# To match cases against their OpenMRS Person UUID, in case config (Project Settings > Data Forwarding > Forward to
# OpenMRS > Configure > Case config) "patient_identifiers", set the identifier's key to the value of
# PERSON_UUID_IDENTIFIER_TYPE_ID. e.g.::
#
#     "patient_identifiers": {
#         /* ... */
#         "uuid": {
#             "doc_type": "CaseProperty",
#             "case_property": "openmrs_uuid",
#         }
#     }
#
# To match against any other OpenMRS identifier, set the key to the UUID of the OpenMRS Identifier Type. e.g.::
#
#     "patient_identifiers": {
#         /* ... */
#         "e2b966d0-1d5f-11e0-b929-000c29ad1d07": {
#             "doc_type": "CaseProperty",
#             "case_property": "nid"
#         }
#     }
#
PERSON_UUID_IDENTIFIER_TYPE_ID = 'uuid'


OpenmrsResponse = namedtuple('OpenmrsResponse', 'status_code reason')


class Requests(object):
    def __init__(self, base_url, username, password):
        import requests
        self.requests = requests
        self.base_url = base_url
        self.username = username
        self.password = password

    def get_url(self, uri):
        return '/'.join((self.base_url.rstrip('/'), uri.lstrip('/')))

    def delete(self, uri, **kwargs):
        return self.requests.delete(self.get_url(uri),
                                    auth=(self.username, self.password), **kwargs)

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


def get_case_location(case):
    """
    If the owner of the case is a location, return it. Otherwise return
    the owner's primary location. If the case owner does not have a
    primary location, return None.
    """
    case_owner = get_wrapped_owner(get_owner_id(case))
    if isinstance(case_owner, SQLLocation):
        return case_owner
    location_id = case_owner.get_location_id(case.domain)
    return SQLLocation.by_location_id(location_id) if location_id else None


def get_case_location_ancestor_repeaters(case):
    """
    Determine the location of the case's owner, and search up its
    ancestors to find the first OpenMRS Repeater(s).

    Returns a list because more than one OpenmrsRepeater may have the
    same location.
    """
    from corehq.motech.openmrs.dbaccessors import get_openmrs_repeaters_by_domain

    case_location = get_case_location(case)
    if not case_location:
        return []
    location_repeaters = defaultdict(list)
    for repeater in get_openmrs_repeaters_by_domain(case.domain):
        if repeater.location_id:
            location_repeaters[repeater.location_id].append(repeater)
    for location_id in reversed(case_location.path):
        if location_id in location_repeaters:
            return location_repeaters[location_id]
    return []


def create_person_attribute(requests, person_uuid, attribute_type_uuid, value):
    return requests.post('/ws/rest/v1/person/{person_uuid}/attribute'.format(
        person_uuid=person_uuid), json={
            'attributeType': attribute_type_uuid,
            'value': value,
        },
    ).json()


@task
def delete_person_attribute_task(requests, person_uuid, attribute_uuid):
    return requests.delete('/ws/rest/v1/person/{person_uuid}/attribute/{attribute_uuid}'.format(
        person_uuid=person_uuid, attribute_uuid=attribute_uuid
    )).json()


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


class CreateVisitTask(WorkflowTask):

    def run(self, requests, person_uuid, provider_uuid, visit_datetime, values_for_concept, encounter_type,
            openmrs_form, visit_type, location_uuid=None):

        start_datetime = server_datetime_to_openmrs_timestamp(visit_datetime)
        stop_datetime = server_datetime_to_openmrs_timestamp(
            visit_datetime + timedelta(days=1) - timedelta(seconds=1)
        )

        visit = {
            'patient': person_uuid,
            'visitType': visit_type,
            'startDatetime': start_datetime,
            'stopDatetime': stop_datetime,
        }
        if location_uuid:
            visit['location'] = location_uuid
        response = requests.post_with_raise('/ws/rest/v1/visit', json=visit)
        visit_uuid = response.json()['uuid']

        self._subtasks.append(
            CreateEncounterTask(
                None,
                delete_encounter_task(requests),  # `encounter_uuid` doesn't need to be passed yet.
                'encounter_uuid',                     # execute_workflow() sets the rollback task's kwargs later
                requests, person_uuid, provider_uuid, start_datetime, values_for_concept, encounter_type,
                openmrs_form, visit_uuid, location_uuid,
            )
        )

        return visit_uuid


@task
def delete_visit_task(requests, visit_uuid):
    return requests.delete('/ws/rest/v1/visit/{uuid}'.format(uuid=visit_uuid)).json()


class CreateEncounterTask(WorkflowTask):

    def run(self, requests, person_uuid, provider_uuid, start_datetime, values_for_concept, encounter_type,
            openmrs_form, visit_uuid, location_uuid=None):

        encounter = {
            'encounterDatetime': start_datetime,
            'patient': person_uuid,
            'form': openmrs_form,
            'encounterType': encounter_type,
            'visit': visit_uuid,
        }
        if location_uuid:
            encounter['location'] = location_uuid
        if provider_uuid:
            # TODO: Verify. See commented-out section below
            encounter['provider'] = provider_uuid
        response = requests.post_with_raise('/ws/rest/v1/encounter', json=encounter)
        encounter_uuid = response.json()['uuid']

        # TODO: This is suspicious. Doesn't match docs. If it's true, add it as a subtask
        # if provider_uuid:
        #     encounter_provider = {'provider': provider_uuid}
        #     uri = '/ws/rest/v1/encounter/{uuid}/encounterprovider'.format(uuid=encounter_uuid)
        #     requests.post_with_raise(uri, json=encounter_provider)

        for concept_uuid, values in values_for_concept.items():
            for value in values:

                self._subtasks.append(
                    WorkflowTask(
                        create_obs,
                        delete_obs_task(requests),
                        'obs_uuid',
                        requests, encounter_uuid, concept_uuid, person_uuid, start_datetime, value, location_uuid,
                    )
                )

        return encounter_uuid


@task
def delete_encounter_task(requests, encounter_uuid):
    return requests.delete('/ws/rest/v1/encounter/{uuid}'.format(uuid=encounter_uuid)).json()


def create_obs(requests, encounter_uuid, concept_uuid, person_uuid, start_datetime, value, location_uuid=None):
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
    return response.json()['uuid']


@task
def delete_obs_task(requests, obs_uuid):
    return requests.delete('/ws/rest/v1/obs/{uuid}'.format(uuid=obs_uuid)).json()


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


@task
def rollback_person_name_task(requests, person, openmrs_config):
    """
    Reset the name changes previously set by `update_person_name()` back to their original values, which are
    taken from the patient details that OpenMRS returned at the start of the workflow.
    """
    properties = {
        property_: person['preferredName'][property_]
        for property_ in openmrs_config.case_config.person_preferred_name.keys()
        if property_ in NAME_PROPERTIES
    }
    if properties:
        requests.post_with_raise(
            '/ws/rest/v1/person/{person_uuid}/name/{name_uuid}'.format(
                person_uuid=person['uuid'],
                name_uuid=person['preferredName']['uuid'],
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


@task
def delete_person_address_task(requests, person, address_uuid):
    requests.post_with_raise(
        '/ws/rest/v1/person/{person_uuid}/address/{address_uuid}'.format(
            person_uuid=person['uuid'],
            address_uuid=address_uuid,
        )
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


@task
def rollback_person_address_task(requests, person, openmrs_config):
    properties = {
        property_: person['preferredAddress'][property_]
        for property_ in openmrs_config.case_config.person_preferred_address.keys()
        if property_ in ADDRESS_PROPERTIES
    }
    if properties:
        requests.post_with_raise(
            '/ws/rest/v1/person/{person_uuid}/address/{address_uuid}'.format(
                person_uuid=person['uuid'],
                address_uuid=person['preferredAddress']['uuid'],
            ),
            json=properties,
        )


def get_subresource_instances(requests, person_uuid, subresource):
    assert subresource in PERSON_SUBRESOURCES
    return requests.get('/ws/rest/v1/person/{person_uuid}/{subresource}'.format(
        person_uuid=person_uuid,
        subresource=subresource,
    )).json()['results']


def find_patient(requests, domain, case_id, openmrs_config):
    case = CaseAccessors(domain).get_case(case_id)
    patient_finder = PatientFinder.wrap(openmrs_config.case_config.patient_finder)
    patients = patient_finder.find_patients(requests, case, openmrs_config.case_config)
    # If PatientFinder can't narrow down the number of candidate
    # patients, don't guess. Just admit that we don't know.
    return patients[0] if len(patients) == 1 else None


def get_patient(requests, domain, info, openmrs_config):
    patient = None
    for id_ in openmrs_config.case_config.match_on_ids:
        identifier = openmrs_config.case_config.patient_identifiers[id_]
        # identifier.case_property must be in info.extra_fields because OpenmrsRepeater put it there
        assert identifier.case_property in info.extra_fields, 'identifier case_property missing from extra_fields'
        patient = get_patient_by_id(requests, id_, info.extra_fields[identifier.case_property])
        if patient:
            break
    else:
        # Definitive IDs did not match a patient in OpenMRS.
        if openmrs_config.case_config.patient_finder:
            # Search for patients based on other case properties
            logger.debug(
                'Case %s did not match patient with OpenmrsCaseConfig.match_on_ids. Search using '
                'PatientFinder "%s"', info.case_id, openmrs_config.case_config.patient_finder['doc_type'],
            )
            patient = find_patient(requests, domain, info.case_id, openmrs_config)

    return patient


def update_person_properties(requests, info, openmrs_config, person_uuid):
    properties = {
        property_: value_source.get_value(info)
        for property_, value_source in openmrs_config.case_config.person_properties.items()
        if property_ in PERSON_PROPERTIES and value_source.get_value(info)
    }
    if properties:
        requests.post_with_raise(
            '/ws/rest/v1/person/{person_uuid}'.format(person_uuid=person_uuid),
            json=properties
        )


@task
def rollback_person_properties_task(requests, person, openmrs_config):
    """
    Reset the properties previously set by `update_person_properties()` back to their original values, which are
    taken from the patient details that OpenMRS returned at the start of the workflow.
    """
    properties = {
        property_: person[property_]
        for property_ in openmrs_config.case_config.person_properties.keys()
        if property_ in PERSON_PROPERTIES
    }
    if properties:
        requests.post_with_raise(
            '/ws/rest/v1/person/{person_uuid}'.format(person_uuid=person['uuid']),
            json=properties
        )


class PatientSearchParser(object):
    def __init__(self, response_json):
        self.response_json = response_json

    def get_patient_matching_identifiers(self, patient_identifier_type, patient_identifier):
        """
        Return the patient that matches the given identifier. If the
        number of matches is zero or more than one, return None.

        :param patient_identifier_type: PERSON_UUID_IDENTIFIER_TYPE_ID
            to match the patient's OpenMRS Person UUID, otherwise the
            UUID of the OpenMRS identifier type
        :param patient_identifier: The value that uniquely identifies
            the patient we want.

        """
        patients = []
        for patient in self.response_json['results']:
            if (
                patient_identifier_type == PERSON_UUID_IDENTIFIER_TYPE_ID and
                patient['uuid'] == patient_identifier
            ):
                patients.append(patient)
            else:
                for identifier in patient['identifiers']:
                    if (
                        identifier['identifier'] == patient_identifier and
                        identifier['identifierType']['uuid'] == patient_identifier_type
                    ):
                        patients.append(patient)
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

    >>> values = get_form_question_values({'form': {'foo': {'bar': 'baz'}}})
    >>> values == {'/data/foo/bar': 'baz'}
    True

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
                question = '/'.join((p.decode('utf8') if isinstance(p, bytes) else p for p in new_path))
                result_[question] = value

    result = {}
    _recurse_form_questions(form_json['form'], [b'/data'], result)  # "/data" is just convention, hopefully
    # familiar from form builder. The form's data will usually be immediately under "form_json['form']" but not
    # necessarily. If this causes problems we may need a more reliable way to get to it.
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
