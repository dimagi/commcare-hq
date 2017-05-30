from custom.infomovel_fgh.openmrs.field_mappings import IdMatcher
from custom.infomovel_fgh.openmrs.repeater_helpers import CaseTriggerInfo, get_patient_by_id


def send_openmrs_data(requests, form_json, case_trigger_infos, id_matchers):
    problem_log = []
    for info in case_trigger_infos:
        assert isinstance(info, CaseTriggerInfo)
        sync_openmrs_patient(requests, info, id_matchers, problem_log)


def sync_openmrs_patient(requests, info, id_matchers, problem_log):
    for id_matcher in id_matchers:
        assert isinstance(id_matcher, IdMatcher)
        if id_matcher.case_property in info.extra_fields:
            patient = get_patient_by_id(
                requests, id_matcher.identifier_type,
                info.extra_fields[id_matcher.case_property])
            if patient:
                break
    else:
        problem_log.append("Could not find patient matching case")
        return

    patient_uuid = patient['uuid']
