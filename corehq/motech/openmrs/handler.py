from corehq.motech.openmrs.logger import logger
from corehq.motech.openmrs.openmrs_config import IdMatcher
from corehq.motech.openmrs.repeater_helpers import CaseTriggerInfo, get_patient_by_id, \
    update_person_attribute, create_person_attribute, create_visit, set_person_properties
from dimagi.utils.parsing import string_to_utc_datetime


def send_openmrs_data(requests, form_json, case_trigger_infos, openmrs_config):
    problem_log = []
    person_uuids = []
    logger.debug(case_trigger_infos)
    for info in case_trigger_infos:
        assert isinstance(info, CaseTriggerInfo)
        # todo: create patient if it doesn't exist?
        person_uuid = sync_openmrs_patient(requests, info, openmrs_config, problem_log)
        person_uuids.append(person_uuid)

    logger.debug(person_uuids)
    # todo: find a better way to correlate to the correct or "main" patient
    if len(person_uuids) == 1 and all(person_uuid for person_uuid in person_uuids):
        person_uuid, = person_uuids
        info, = case_trigger_infos
        for form_config in openmrs_config.form_configs:
            logger.debug('send_openmrs_visit?', form_config, form_json)
            if form_config.xmlns == form_json['form']['@xmlns']:
                logger.debug('yes')
                send_openmrs_visit(requests, info, form_config, person_uuid,
                                   visit_datetime=string_to_utc_datetime(form_json['form']['meta']['timeEnd']))


def send_openmrs_visit(requests, info, form_config, person_uuid, visit_datetime):
    create_visit(
        requests,
        person_uuid=person_uuid,
        visit_datetime=visit_datetime,
        values_for_concept={obs.concept: [obs.value.get_value(info)]
                            for obs in form_config.openmrs_observations
                            if obs.value.get_value(info)},
        encounter_type=form_config.openmrs_encounter_type,
        openmrs_form=form_config.openmrs_form,
        visit_type=form_config.openmrs_visit_type,
    )


def sync_openmrs_patient(requests, info, openmrs_config, problem_log):
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

    person_uuid = patient['person']['uuid']

    # update properties

    properties = {
        person_property: value_source.get_value(info)
        for person_property, value_source in openmrs_config.case_config.person_properties.items()
        if value_source.get_value(info)
    }
    set_person_properties(requests, person_uuid, properties)

    # update attributes

    existing_person_attributes = {
        attribute['attributeType']['uuid']: (attribute['uuid'], attribute['value'])
        for attribute in patient['person']['attributes']
    }

    for person_attribute_type, value_source in openmrs_config.case_config.person_attributes.items():
        value = value_source.get_value(info)
        if person_attribute_type in existing_person_attributes:
            attribute_uuid, existing_value = existing_person_attributes[person_attribute_type]
            if value != existing_value:
                update_person_attribute(requests, person_uuid, attribute_uuid, person_attribute_type, value)
        else:
            create_person_attribute(requests, person_uuid, person_attribute_type, value)

    return person_uuid
