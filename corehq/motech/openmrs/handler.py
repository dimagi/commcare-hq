from __future__ import absolute_import
from __future__ import unicode_literals

from corehq.motech.openmrs.logger import logger
from corehq.motech.openmrs.repeater_helpers import (
    CaseTriggerInfo,
    CreatePersonAddressTask,
    CreatePersonAttributeTask,
    CreateVisitTask,
    OpenmrsResponse,
    UpdatePersonAddressTask,
    UpdatePersonAttributeTask,
    UpdatePersonNameTask,
    UpdatePersonPropertiesTask,
    get_openmrs_location_uuid,
    get_patient,
)
from corehq.motech.openmrs.workflow import WorkflowTask, execute_workflow
from corehq.motech.utils import pformat_json
from dimagi.utils.parsing import string_to_utc_datetime


def send_openmrs_data(requests, domain, form_json, openmrs_config, case_trigger_infos, form_question_values):
    """
    Updates an OpenMRS patient and (optionally) creates visits.

    This involves several requests to the `OpenMRS REST Web Services`_. If any of those requests fail, we want to
    roll back previous changes to avoid inconsistencies in OpenMRS. To do this we define a workflow of tasks we
    want to do. Each workflow task has a rollback task. If a task fails, all previous tasks are rolled back in
    reverse order.

    :return: A response-like object that can be used by Repeater.handle_response


    .. _OpenMRS REST Web Services: https://wiki.openmrs.org/display/docs/REST+Web+Services+API+For+Clients
    """
    workflow = []
    for info in case_trigger_infos:
        workflow.append(
            SyncOpenmrsPatientTask(requests, domain, info, form_json, form_question_values, openmrs_config)
        )

    errors = execute_workflow(workflow)
    if errors:
        logger.error('Errors encountered sending OpenMRS data: %s', errors)
        return OpenmrsResponse(400, 'Bad Request', pformat_json([str(e) for e in errors]))
    else:
        return OpenmrsResponse(200, 'OK', '')


class SyncPersonAttributesTask(WorkflowTask):

    def __init__(self, requests, info, openmrs_config, person_uuid, attributes):
        self.requests = requests
        self.info = info
        self.openmrs_config = openmrs_config
        self.person_uuid = person_uuid
        self.attributes = attributes

    def run(self):
        """
        Returns WorkflowTasks for creating and updating OpenMRS person attributes.
        """
        subtasks = []
        existing_person_attributes = {
            attribute['attributeType']['uuid']: (attribute['uuid'], attribute['value'])
            for attribute in self.attributes
        }
        for person_attribute_type, value_source in self.openmrs_config.case_config.person_attributes.items():
            value = value_source.get_value(self.info)
            if person_attribute_type in existing_person_attributes:
                attribute_uuid, existing_value = existing_person_attributes[person_attribute_type]
                if value != existing_value:
                    subtasks.append(
                        UpdatePersonAttributeTask(
                            self.requests, self.person_uuid, attribute_uuid, person_attribute_type, value,
                            existing_value
                        )
                    )
            else:
                subtasks.append(
                    CreatePersonAttributeTask(self.requests, self.person_uuid, person_attribute_type, value)
                )
        return subtasks


class CreateVisitsTask(WorkflowTask):

    def __init__(self, requests, domain, info, form_json, form_question_values, openmrs_config, person_uuid):
        self.requests = requests
        self.domain = domain
        self.info = info
        self.form_json = form_json
        self.form_question_values = form_question_values
        self.openmrs_config = openmrs_config
        self.person_uuid = person_uuid

    def run(self):
        """
        Returns WorkflowTasks for creating visits, encounters and observations
        """
        subtasks = []
        provider_uuid = getattr(self.openmrs_config, 'openmrs_provider', None)
        location_uuid = get_openmrs_location_uuid(self.domain, self.info.case_id)
        self.info.form_question_values.update(self.form_question_values)
        for form_config in self.openmrs_config.form_configs:
            logger.debug('Send visit for form?', form_config, self.form_json)
            if form_config.xmlns == self.form_json['form']['@xmlns']:
                logger.debug('Yes')

                subtasks.append(
                    CreateVisitTask(
                        self.requests,
                        person_uuid=self.person_uuid,
                        provider_uuid=provider_uuid,
                        visit_datetime=string_to_utc_datetime(self.form_json['form']['meta']['timeEnd']),
                        values_for_concept={obs.concept: [obs.value.get_value(self.info)]
                                            for obs in form_config.openmrs_observations
                                            if obs.value.get_value(self.info)},
                        encounter_type=form_config.openmrs_encounter_type,
                        openmrs_form=form_config.openmrs_form,
                        visit_type=form_config.openmrs_visit_type,
                        location_uuid=location_uuid,
                    )
                )
        return subtasks


class SyncOpenmrsPatientTask(WorkflowTask):

    def __init__(self, requests, domain, info, form_json, form_question_values, openmrs_config):
        self.requests = requests
        self.domain = domain
        self.info = info
        self.form_json = form_json
        self.form_question_values = form_question_values
        self.openmrs_config = openmrs_config

    def run(self):
        subtasks = []
        assert isinstance(self.info, CaseTriggerInfo)
        logger.debug('Fetching OpenMRS patient UUID with ', self.info)
        patient = get_patient(self.requests, self.domain, self.info, self.openmrs_config)
        if patient is None:
            raise ValueError('CommCare patient was not found in OpenMRS')
        person_uuid = patient['person']['uuid']
        logger.debug('OpenMRS patient found: ', person_uuid)

        subtasks.extend([
            UpdatePersonPropertiesTask(self.requests, self.info, self.openmrs_config, patient['person']),

            UpdatePersonNameTask(self.requests, self.info, self.openmrs_config, patient['person'])
        ])

        if patient['person']['preferredAddress']:
            subtasks.append(
                UpdatePersonAddressTask(self.requests, self.info, self.openmrs_config, patient['person'])
            )
        else:
            subtasks.append(
                CreatePersonAddressTask(self.requests, self.info, self.openmrs_config, patient['person'])
            )

        subtasks.extend([
            SyncPersonAttributesTask(
                self.requests, self.info, self.openmrs_config, person_uuid, patient['person']['attributes']
            ),

            CreateVisitsTask(
                self.requests, self.domain, self.info, self.form_json, self.form_question_values,
                self.openmrs_config, person_uuid
            ),
        ])

        return subtasks
