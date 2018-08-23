from __future__ import absolute_import
from __future__ import unicode_literals

from collections import namedtuple, defaultdict
from datetime import timedelta
from itertools import chain
import re

from requests import RequestException
import six
from six.moves import zip

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.xform import extract_case_blocks
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.cases import get_wrapped_owner, get_owner_id
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.motech.openmrs.const import (
    ADDRESS_PROPERTIES,
    LOCATION_OPENMRS_UUID,
    NAME_PROPERTIES,
    PERSON_PROPERTIES,
    PERSON_UUID_IDENTIFIER_TYPE_ID,
    XMLNS_OPENMRS,
)
from corehq.motech.openmrs.finders import PatientFinder
from corehq.motech.openmrs.serializers import to_timestamp
from corehq.motech.openmrs.workflow import WorkflowTask
from corehq.motech.value_source import CaseTriggerInfo

OpenmrsResponse = namedtuple('OpenmrsResponse', 'status_code reason content')


def serialize(data):
    """
    Convert values in data to a format OpenMRS will accept.

    >>> serialize({'birthdate': '2017-06-27'}) == {'birthdate': '2017-06-27T00:00:00.000+0000'}
    True

    """
    # We can get away with not worrying about namespaces because these
    # property names are fixed and unique.
    serializers = dict(chain(six.iteritems(ADDRESS_PROPERTIES), six.iteritems(NAME_PROPERTIES), six.iteritems(PERSON_PROPERTIES)))
    return {p: serializers[p](v) if serializers[p] else v for p, v in data.items()}


def get_case_location(case):
    """
    If the owner of the case is a location, return it. Otherwise return
    the owner's primary location. If the case owner does not have a
    primary location, return None.
    """
    case_owner = get_wrapped_owner(get_owner_id(case))
    if not case_owner:
        return None
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
    from corehq.motech.openmrs.repeaters import OpenmrsRepeater

    case_location = get_case_location(case)
    if not case_location:
        return []
    location_repeaters = defaultdict(list)
    for repeater in OpenmrsRepeater.by_domain(case.domain):
        if repeater.location_id:
            location_repeaters[repeater.location_id].append(repeater)
    for location_id in reversed(case_location.path):
        if location_id in location_repeaters:
            return location_repeaters[location_id]
    return []


def get_openmrs_location_uuid(domain, case_id):
    case = CaseAccessors(domain).get_case(case_id)
    location = get_case_location(case)
    return location.metadata.get(LOCATION_OPENMRS_UUID) if location else None


class CreatePersonAttributeTask(WorkflowTask):

    def __init__(self, requests, person_uuid, attribute_type_uuid, value):
        self.requests = requests
        self.person_uuid = person_uuid
        self.attribute_type_uuid = attribute_type_uuid
        self.value = value
        self.attribute_uuid = None

    def run(self):
        response = self.requests.post(
            '/ws/rest/v1/person/{person_uuid}/attribute'.format(person_uuid=self.person_uuid),
            json={'attributeType': self.attribute_type_uuid, 'value': self.value},
            raise_for_status=True,
        )
        self.attribute_uuid = response.json()['uuid']

    def rollback(self):
        # if attribute_uuid is not set, it would be because the workflow task to create the attribute failed
        if self.attribute_uuid:
            self.requests.delete(
                '/ws/rest/v1/person/{person_uuid}/attribute/{attribute_uuid}'.format(
                    person_uuid=self.person_uuid, attribute_uuid=self.attribute_uuid
                ),
                raise_for_status=True,
            )


class UpdatePersonAttributeTask(WorkflowTask):

    def __init__(self, requests, person_uuid, attribute_uuid, attribute_type_uuid, value, existing_value):
        self.requests = requests
        self.person_uuid = person_uuid
        self.attribute_uuid = attribute_uuid
        self.attribute_type_uuid = attribute_type_uuid
        self.value = value
        self.existing_value = existing_value

    def run(self):
        self.requests.post(
            '/ws/rest/v1/person/{person_uuid}/attribute/{attribute_uuid}'.format(
                person_uuid=self.person_uuid, attribute_uuid=self.attribute_uuid
            ),
            json={
                'value': self.value,
                'attributeType': self.attribute_type_uuid,
            },
            raise_for_status=True,
        )

    def rollback(self):
        self.requests.post(
            '/ws/rest/v1/person/{person_uuid}/attribute/{attribute_uuid}'.format(
                person_uuid=self.person_uuid, attribute_uuid=self.attribute_uuid
            ),
            json={
                'value': self.existing_value,
                'attributeType': self.attribute_type_uuid,
            },
            raise_for_status=True,
        )


class CreatePatientIdentifierTask(WorkflowTask):

    def __init__(self, requests, patient_uuid, identifier_type_uuid, identifier):
        self.requests = requests
        self.patient_uuid = patient_uuid
        self.identifier_type_uuid = identifier_type_uuid
        self.identifier = identifier
        self.identifier_uuid = None

    def run(self):
        response = self.requests.post(
            '/ws/rest/v1/patient/{patient_uuid}/identifier'.format(patient_uuid=self.patient_uuid),
            json={'identifierType': self.identifier_type_uuid, 'identifier': self.identifier},
            raise_for_status=True,
        )
        self.identifier_uuid = response.json()['uuid']

    def rollback(self):
        if self.identifier_uuid:
            self.requests.delete(
                '/ws/rest/v1/patient/{patient_uuid}/identifier/{identifier_uuid}'.format(
                    patient_uuid=self.patient_uuid, identifier_uuid=self.identifier_uuid
                ),
                raise_for_status=True,
            )


class UpdatePatientIdentifierTask(WorkflowTask):

    def __init__(self, requests, patient_uuid, identifier_uuid, identifier_type_uuid, identifier,
                 existing_identifier):
        self.requests = requests
        self.patient_uuid = patient_uuid
        self.identifier_uuid = identifier_uuid
        self.identifier_type_uuid = identifier_type_uuid
        self.identifier = identifier
        self.existing_identifier = existing_identifier

    def run(self):
        self.requests.post(
            '/ws/rest/v1/patient/{patient_uuid}/identifier/{identifier_uuid}'.format(
                patient_uuid=self.patient_uuid, identifier_uuid=self.identifier_uuid
            ),
            json={
                'identifier': self.identifier,
                'identifierType': self.identifier_type_uuid,
            },
            raise_for_status=True,
        )

    def rollback(self):
        self.requests.post(
            '/ws/rest/v1/patient/{patient_uuid}/identifier/{identifier_uuid}'.format(
                patient_uuid=self.patient_uuid, identifier_uuid=self.identifier_uuid
            ),
            json={
                'identifier': self.existing_identifier,
                'identifierType': self.identifier_type_uuid,
            },
            raise_for_status=True,
        )


class CreateVisitTask(WorkflowTask):

    def __init__(self, requests, person_uuid, provider_uuid, visit_datetime, values_for_concept, encounter_type,
                 openmrs_form, visit_type, location_uuid=None):
        self.requests = requests
        self.person_uuid = person_uuid
        self.provider_uuid = provider_uuid
        self.visit_datetime = visit_datetime
        self.values_for_concept = values_for_concept
        self.encounter_type = encounter_type
        self.openmrs_form = openmrs_form
        self.visit_type = visit_type
        self.location_uuid = location_uuid
        self.visit_uuid = None

    def run(self):
        subtasks = []
        start_datetime = to_timestamp(self.visit_datetime)
        if self.visit_type:
            stop_datetime = to_timestamp(
                self.visit_datetime + timedelta(days=1) - timedelta(seconds=1)
            )
            visit = {
                'patient': self.person_uuid,
                'visitType': self.visit_type,
                'startDatetime': start_datetime,
                'stopDatetime': stop_datetime,
            }
            if self.location_uuid:
                visit['location'] = self.location_uuid
            response = self.requests.post('/ws/rest/v1/visit', json=visit, raise_for_status=True)
            self.visit_uuid = response.json()['uuid']

        subtasks.append(
            CreateEncounterTask(
                self.requests, self.person_uuid, self.provider_uuid, start_datetime, self.values_for_concept,
                self.encounter_type, self.openmrs_form, self.visit_uuid, self.location_uuid
            )
        )
        return subtasks

    def rollback(self):
        if self.visit_uuid:
            self.requests.delete('/ws/rest/v1/visit/{uuid}'.format(uuid=self.visit_uuid), raise_for_status=True)


class CreateEncounterTask(WorkflowTask):

    def __init__(self, requests, person_uuid, provider_uuid, start_datetime, values_for_concept, encounter_type,
                 openmrs_form, visit_uuid, location_uuid=None):
        self.requests = requests
        self.person_uuid = person_uuid
        self.provider_uuid = provider_uuid
        self.start_datetime = start_datetime
        self.values_for_concept = values_for_concept
        self.encounter_type = encounter_type
        self.openmrs_form = openmrs_form
        self.visit_uuid = visit_uuid
        self.location_uuid = location_uuid
        self.encounter_uuid = None

    def run(self):
        subtasks = []
        encounter = {
            'encounterDatetime': self.start_datetime,
            'patient': self.person_uuid,
            'form': self.openmrs_form,
            'encounterType': self.encounter_type,
        }
        if self.visit_uuid:
            encounter['visit'] = self.visit_uuid
        if self.location_uuid:
            encounter['location'] = self.location_uuid
        if self.provider_uuid:
            encounter['provider'] = self.provider_uuid
        response = self.requests.post('/ws/rest/v1/encounter', json=encounter, raise_for_status=True)
        self.encounter_uuid = response.json()['uuid']

        for concept_uuid, values in self.values_for_concept.items():
            for value in values:
                subtasks.append(
                    CreateObsTask(
                        self.requests, self.encounter_uuid, concept_uuid, self.person_uuid, self.start_datetime,
                        value, self.location_uuid
                    )
                )
        return subtasks

    def rollback(self):
        if self.encounter_uuid:
            self.requests.delete(
                '/ws/rest/v1/encounter/{uuid}'.format(uuid=self.encounter_uuid), raise_for_status=True
            )


class CreateObsTask(WorkflowTask):

    def __init__(self, requests, encounter_uuid, concept_uuid, person_uuid, start_datetime, value,
                 location_uuid=None):
        self.requests = requests
        self.encounter_uuid = encounter_uuid
        self.concept_uuid = concept_uuid
        self.person_uuid = person_uuid
        self.start_datetime = start_datetime
        self.value = value
        self.location_uuid = location_uuid
        self.obs_uuid = None

    def run(self):
        observation = {
            'concept': self.concept_uuid,
            'person': self.person_uuid,
            'obsDatetime': self.start_datetime,
            'encounter': self.encounter_uuid,
            'value': self.value,
        }
        if self.location_uuid:
            observation['location'] = self.location_uuid
        response = self.requests.post('/ws/rest/v1/obs', json=observation, raise_for_status=True)
        self.obs_uuid = response.json()['uuid']

    def rollback(self):
        if self.obs_uuid:
            self.requests.delete('/ws/rest/v1/obs/{uuid}'.format(uuid=self.obs_uuid), raise_for_status=True)


def search_patients(requests, search_string):
    response = requests.get('/ws/rest/v1/patient', {'q': search_string, 'v': 'full'}, raise_for_status=True)
    return response.json()


def get_patient_by_uuid(requests, uuid):
    if not uuid:
        return None
    if not re.match(r'^[a-fA-F0-9\-]{36}$', uuid):
        # UUID should come from OpenMRS. If this ever happens we want to know about it.
        raise ValueError('Person UUID "{}" failed validation'.format(uuid))
    response = requests.get('/ws/rest/v1/patient/' + uuid, {'v': 'full'}, raise_for_status=True)
    return response.json()


def get_patient_by_identifier(requests, identifier_type_uuid, value):
    """
    Return the patient that matches the given identifier. If the
    number of matches is zero or more than one, return None.
    """
    response_json = search_patients(requests, value)
    patients = []
    for patient in response_json['results']:
        for identifier in patient['identifiers']:
            if (
                identifier['identifierType']['uuid'] == identifier_type_uuid and
                identifier['identifier'] == value
            ):
                patients.append(patient)
    try:
        patient, = patients
    except ValueError:
        return None
    else:
        return patient


def get_patient_by_id(requests, patient_identifier_type, patient_identifier):
    # Fetching the patient is the first request sent to the server. If
    # there is a mistake in the server details, or the server is
    # offline, this is where we will discover it.
    try:
        if patient_identifier_type == PERSON_UUID_IDENTIFIER_TYPE_ID:
            return get_patient_by_uuid(requests, patient_identifier)
        else:
            return get_patient_by_identifier(requests, patient_identifier_type, patient_identifier)
    except RequestException as err:
        # This message needs to be useful to an administrator because
        # it will be shown in the Repeat Records report.
        http_error_msg = (
            'An error was when encountered searching patients: {}. Please check that the server is online. If '
            'this is a new forwarding location, please check the server address in Data Forwarding, check that '
            'the server URL includes the path to the API, and that the password is correct'.format(err)
        )
        raise err.__class__(http_error_msg)


class UpdatePersonNameTask(WorkflowTask):

    def __init__(self, requests, info, openmrs_config, person):
        self.requests = requests
        self.info = info
        self.openmrs_config = openmrs_config
        self.person = person
        self.person_uuid = person['uuid']
        self.name_uuid = person['preferredName']['uuid']

    def run(self):
        properties = {
            property_: value_source.get_value(self.info)
            for property_, value_source in self.openmrs_config.case_config.person_preferred_name.items()
            if property_ in NAME_PROPERTIES and value_source.get_value(self.info)
        }
        if properties:
            self.requests.post(
                '/ws/rest/v1/person/{person_uuid}/name/{name_uuid}'.format(
                    person_uuid=self.person_uuid,
                    name_uuid=self.name_uuid,
                ),
                json=serialize(properties),
                raise_for_status=True,
            )

    def rollback(self):
        """
        Reset the name changes back to their original values, which are
        taken from the patient details that OpenMRS returned at the
        start of the workflow.
        """
        properties = {
            property_: self.person['preferredName'].get(property_)
            for property_ in self.openmrs_config.case_config.person_preferred_name.keys()
            if property_ in NAME_PROPERTIES
        }
        if properties:
            self.requests.post(
                '/ws/rest/v1/person/{person_uuid}/name/{name_uuid}'.format(
                    person_uuid=self.person_uuid,
                    name_uuid=self.name_uuid,
                ),
                json=serialize(properties),
                raise_for_status=True,
            )


class CreatePersonAddressTask(WorkflowTask):

    def __init__(self, requests, info, openmrs_config, person):
        self.requests = requests
        self.info = info
        self.openmrs_config = openmrs_config
        self.person = person
        self.person_uuid = person['uuid']
        self.address_uuid = None

    def run(self):
        properties = {
            property_: value_source.get_value(self.info)
            for property_, value_source in self.openmrs_config.case_config.person_preferred_address.items()
            if property_ in ADDRESS_PROPERTIES and value_source.get_value(self.info)
        }
        if properties:
            response = self.requests.post(
                '/ws/rest/v1/person/{person_uuid}/address/'.format(person_uuid=self.person_uuid),
                json=serialize(properties),
                raise_for_status=True,
            )
            self.address_uuid = response.json()['uuid']

    def rollback(self):
        if self.address_uuid:
            self.requests.delete(
                '/ws/rest/v1/person/{person_uuid}/address/{address_uuid}'.format(
                    person_uuid=self.person_uuid,
                    address_uuid=self.address_uuid,
                ),
                raise_for_status=True,
            )


class UpdatePersonAddressTask(WorkflowTask):

    def __init__(self, requests, info, openmrs_config, person):
        self.requests = requests
        self.info = info
        self.openmrs_config = openmrs_config
        self.person = person
        self.person_uuid = person['uuid']
        self.address_uuid = person['preferredAddress']['uuid']

    def run(self):
        properties = {
            property_: value_source.get_value(self.info)
            for property_, value_source in self.openmrs_config.case_config.person_preferred_address.items()
            if property_ in ADDRESS_PROPERTIES and value_source.get_value(self.info)
        }
        if properties:
            self.requests.post(
                '/ws/rest/v1/person/{person_uuid}/address/{address_uuid}'.format(
                    person_uuid=self.person_uuid,
                    address_uuid=self.address_uuid,
                ),
                json=serialize(properties),
                raise_for_status=True,
            )

    def rollback(self):
        properties = {
            property_: self.person['preferredAddress'].get(property_)
            for property_ in self.openmrs_config.case_config.person_preferred_address.keys()
            if property_ in ADDRESS_PROPERTIES
        }
        if properties:
            self.requests.post(
                '/ws/rest/v1/person/{person_uuid}/address/{address_uuid}'.format(
                    person_uuid=self.person_uuid,
                    address_uuid=self.address_uuid,
                ),
                json=serialize(properties),
                raise_for_status=True,
            )


def save_match_ids(case, case_config, patient):
    """
    If we are confident of the patient matched to a case, save
    the patient's identifiers to the case.
    """
    def get_patient_id_type_uuids_values():
        yield PERSON_UUID_IDENTIFIER_TYPE_ID, patient['uuid']
        for identifier in patient['identifiers']:
            yield identifier['identifierType']['uuid'], identifier['identifier']

    case_config_ids = case_config['patient_identifiers']
    case_update = {}
    kwargs = {}
    for id_type_uuid, value in get_patient_id_type_uuids_values():
        if id_type_uuid in case_config_ids:
            case_property = case_config_ids[id_type_uuid]['case_property']
            if case_property == 'external_id':
                kwargs['external_id'] = value
            else:
                case_update[case_property] = value
    case_block = CaseBlock(
        case_id=case.get_id,
        create=False,
        update=case_update,
        **kwargs
    )
    submit_case_blocks([case_block.as_string()], case.domain, xmlns=XMLNS_OPENMRS)


def find_patient(requests, domain, case_id, openmrs_config):
    case = CaseAccessors(domain).get_case(case_id)
    patient_finder = PatientFinder.wrap(openmrs_config.case_config.patient_finder)
    patients = patient_finder.find_patients(requests, case, openmrs_config.case_config)
    if len(patients) == 1:
        patient, = patients
        save_match_ids(case, openmrs_config.case_config, patient)
        return patient
    # If PatientFinder can't narrow down the number of candidate
    # patients, don't guess. Just admit that we don't know.
    return None


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
            patient = find_patient(requests, domain, info.case_id, openmrs_config)

    return patient


class UpdatePersonPropertiesTask(WorkflowTask):

    def __init__(self, requests, info, openmrs_config, person):
        self.requests = requests
        self.info = info
        self.openmrs_config = openmrs_config
        self.person = person

    def run(self):
        properties = {
            property_: value_source.get_value(self.info)
            for property_, value_source in self.openmrs_config.case_config.person_properties.items()
            if property_ in PERSON_PROPERTIES and value_source.get_value(self.info)
        }
        if properties:
            self.requests.post(
                '/ws/rest/v1/person/{person_uuid}'.format(person_uuid=self.person['uuid']),
                json=serialize(properties),
                raise_for_status=True,
            )

    def rollback(self):
        """
        Reset person properties back to their original values, which
        are taken from the patient details that OpenMRS returned at the
        start of the workflow.
        """
        properties = {
            property_: self.person.get(property_)
            for property_ in self.openmrs_config.case_config.person_properties.keys()
            if property_ in PERSON_PROPERTIES
        }
        if properties:
            self.requests.post(
                '/ws/rest/v1/person/{person_uuid}'.format(person_uuid=self.person['uuid']),
                json=serialize(properties),
                raise_for_status=True,
            )


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
