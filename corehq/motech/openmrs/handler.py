from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.motech.openmrs.logger import logger
from corehq.motech.openmrs.repeater_helpers import (
    CaseTriggerInfo,
    OpenmrsResponse,
    CreateVisitTask,
    delete_visit,
    get_patient,
    update_person_properties,
    rollback_person_properties,
    update_person_name,
    rollback_person_name,
    update_person_address,
    rollback_person_address,
    create_person_address,
    delete_person_address,
    update_person_attribute,
    create_person_attribute,
    delete_person_attribute,
)
from corehq.motech.openmrs.workflow import WorkflowTask, execute_workflow
from corehq.motech.utils import pformat_json, unpack_args
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


class SyncPersonAttrsTask(WorkflowTask):

    def run(self):
        """
        This task does not make any changes itself. It uses subtasks for creating and updating OpenMRS person
        attributes.
        """
        requests, info, openmrs_config, person_uuid, attributes = unpack_args(
            'requests info openmrs_config person_uuid attributes', *self.func_args, **self.func_kwargs
        )

        subtasks = []
        existing_person_attributes = {
            attribute['attributeType']['uuid']: (attribute['uuid'], attribute['value'])
            for attribute in attributes
        }
        for person_attribute_type, value_source in openmrs_config.case_config.person_attributes.items():
            value = value_source.get_value(info)
            if person_attribute_type in existing_person_attributes:
                attribute_uuid, existing_value = existing_person_attributes[person_attribute_type]
                if value != existing_value:
                    subtasks.append(
                        WorkflowTask(
                            func=update_person_attribute,
                            func_args=(requests, person_uuid, attribute_uuid, person_attribute_type, value),
                            rollback_func=update_person_attribute,
                            rollback_args=(requests, person_uuid, attribute_uuid, person_attribute_type,
                                           existing_value),
                        )
                    )
            else:
                subtasks.append(
                    WorkflowTask(
                        func=create_person_attribute,
                        func_args=(requests, person_uuid, person_attribute_type, value),
                        rollback_func=delete_person_attribute,
                        rollback_args=(requests, person_uuid),
                        pass_result=True
                    )
                )
        return subtasks


class CreateVisitsTask(WorkflowTask):

    def run(self):
        """
        This task does not make any changes itself. It uses subtasks for creating visits, encounters and
        observations
        """
        requests, info, form_json, form_question_values, openmrs_config, person_uuid = unpack_args(
            'requests info form_json form_question_values openmrs_config person_uuid',
            *self.func_args, **self.func_kwargs
        )
        subtasks = []

        provider_uuid = getattr(openmrs_config, 'openmrs_provider', None)
        info.form_question_values.update(form_question_values)
        for form_config in openmrs_config.form_configs:
            logger.debug('Send visit for form?', form_config, form_json)
            if form_config.xmlns == form_json['form']['@xmlns']:
                logger.debug('Yes')

                subtasks.append(
                    CreateVisitTask(
                        func=None,
                        func_args=(requests, ),
                        func_kwargs=dict(
                            person_uuid=person_uuid,
                            provider_uuid=provider_uuid,
                            visit_datetime=string_to_utc_datetime(form_json['form']['meta']['timeEnd']),
                            values_for_concept={obs.concept: [obs.value.get_value(info)]
                                                for obs in form_config.openmrs_observations
                                                if obs.value.get_value(info)},
                            encounter_type=form_config.openmrs_encounter_type,
                            openmrs_form=form_config.openmrs_form,
                            visit_type=form_config.openmrs_visit_type,
                            # TODO: Set location = location of case owner (CHW)
                            # location_uuid=location[meta][openmrs_uuid]
                        ),
                        rollback_func=delete_visit,
                        rollback_args=(requests, ),
                        # CreateVisitTask.run() will return visit_uuid: Pass it to delete_visit on rollback
                        pass_result=True
                    )
                )


class SyncOpenmrsPatientTask(WorkflowTask):

    def __init__(self, *args, **kwargs):
        super(SyncOpenmrsPatientTask, self).__init__(func=None, func_args=args, func_kwargs=kwargs)

    def run(self):
        requests, domain, info, form_json, form_question_values, openmrs_config = unpack_args(
            'requests domain info form_json form_question_values openmrs_config',
            *self.func_args, **self.func_kwargs
        )
        subtasks = []

        assert isinstance(info, CaseTriggerInfo)
        logger.debug('Fetching OpenMRS patient UUID with ', info)
        patient = get_patient(requests, domain, info, openmrs_config)
        if patient is None:
            raise ValueError('CommCare patient was not found in OpenMRS')
        person_uuid = patient['person']['uuid']
        logger.debug('OpenMRS patient found: ', person_uuid)

        subtasks.extend([
            WorkflowTask(
                func=update_person_properties,
                func_args=(requests, info, openmrs_config, person_uuid),
                rollback_func=rollback_person_properties,
                rollback_args=(requests, patient['person'], openmrs_config),
            ),

            WorkflowTask(
                func=update_person_name,
                func_args=(requests, info, openmrs_config, person_uuid,
                           patient['person']['preferredName']['uuid']),
                rollback_func=rollback_person_name,
                rollback_args=(requests, patient['person'], openmrs_config),
            ),
        ])

        if patient['person']['preferredAddress']:
            subtasks.append(
                WorkflowTask(
                    func=update_person_address,
                    func_args=(requests, info, openmrs_config, person_uuid,
                               patient['person']['preferredAddress']['uuid']),
                    rollback_func=rollback_person_address,
                    rollback_args=(requests, patient['person'], openmrs_config),
                )
            )

        else:
            subtasks.append(
                WorkflowTask(
                    func=create_person_address,
                    func_args=(requests, info, openmrs_config, person_uuid),
                    rollback_func=delete_person_address,
                    rollback_args=(requests, patient['person']),
                    pass_result=True,
                )
            )

        subtasks.extend([
            SyncPersonAttrsTask(
                func=None,
                func_args=(requests, info, openmrs_config, person_uuid, patient['person']['attributes']),
            ),

            CreateVisitsTask(
                func=None,
                func_args=(requests, info, form_json, form_question_values, openmrs_config, person_uuid),
            )
        ])

        return subtasks
