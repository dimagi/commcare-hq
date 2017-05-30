from custom.infomovel_fgh.openmrs.field_mappings import IdMatcher
from custom.infomovel_fgh.openmrs.repeater_helpers import CaseTriggerInfo, get_patient_by_id, \
    update_person_attribute, create_person_attribute


def send_openmrs_data(requests, form_json, case_trigger_infos, openmrs_config):
    problem_log = []
    for info in case_trigger_infos:
        assert isinstance(info, CaseTriggerInfo)
        sync_openmrs_patient(requests, info, openmrs_config, problem_log)


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
