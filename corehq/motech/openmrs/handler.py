from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.motech.openmrs.logger import logger
from corehq.motech.openmrs.repeater_helpers import (
    CaseTriggerInfo,
    create_visit,
    get_patient,
    update_person_properties,
    update_person_name,
    update_person_address,
    create_person_address,
    sync_person_attributes,
)
from dimagi.utils.parsing import string_to_utc_datetime


def send_openmrs_data(requests, form_json, openmrs_config, case_trigger_infos, form_question_values):
    provider_uuid = getattr(openmrs_config, 'openmrs_provider', None)
    problem_log = []
    person_uuids = []
    logger.debug('Fetching OpenMRS patient UUIDs with ', case_trigger_infos)
    for info in case_trigger_infos:
        assert isinstance(info, CaseTriggerInfo)
        # todo: create patient if it doesn't exist?
        person_uuid = sync_openmrs_patient(requests, info, openmrs_config, problem_log)
        person_uuids.append(person_uuid)

    logger.debug('OpenMRS patient(s) found: ', person_uuids)
    # todo: find a better way to correlate to the correct or "main" patient
    if len(person_uuids) == 1 and all(person_uuid for person_uuid in person_uuids):
        person_uuid, = person_uuids
        info, = case_trigger_infos
        info.form_question_values.update(form_question_values)
        for form_config in openmrs_config.form_configs:
            logger.debug('Send visit for form?', form_config, form_json)
            if form_config.xmlns == form_json['form']['@xmlns']:
                logger.debug('Yes')
                send_openmrs_visit(requests, info, form_config, person_uuid, provider_uuid,
                                   visit_datetime=string_to_utc_datetime(form_json['form']['meta']['timeEnd']))


def send_openmrs_visit(requests, info, form_config, person_uuid, provider_uuid, visit_datetime):
    create_visit(
        requests,
        person_uuid=person_uuid,
        provider_uuid=provider_uuid,
        visit_datetime=visit_datetime,
        values_for_concept={obs.concept: [obs.value.get_value(info)]
                            for obs in form_config.openmrs_observations
                            if obs.value.get_value(info)},
        encounter_type=form_config.openmrs_encounter_type,
        openmrs_form=form_config.openmrs_form,
        visit_type=form_config.openmrs_visit_type,
        # location_uuid=,  # location of case owner (CHW) > location[meta][openmrs_uuid]
    )


def sync_openmrs_patient(requests, info, openmrs_config, problem_log):
    patient = get_patient(requests, info, openmrs_config, problem_log)
    if patient is None:
        raise ValueError('CommCare patient was not found in OpenMRS')
    person_uuid = patient['person']['uuid']
    update_person_properties(requests, info, openmrs_config, person_uuid)

    name_uuid = patient['person']['preferredName']['uuid']
    update_person_name(requests, info, openmrs_config, person_uuid, name_uuid)

    address_uuid = patient['person']['preferredAddress']['uuid'] if patient['person']['preferredAddress'] else None
    if address_uuid:
        update_person_address(requests, info, openmrs_config, person_uuid, address_uuid)
    else:
        create_person_address(requests, info, openmrs_config, person_uuid)

    sync_person_attributes(requests, info, openmrs_config, person_uuid, patient['person']['attributes'])

    return person_uuid
