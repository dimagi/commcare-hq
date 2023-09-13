from corehq.apps.data_interfaces.models import CaseRuleActionResult
from corehq.apps.hqcase.utils import update_case, AUTO_UPDATE_XMLNS
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.models import CommCareCase
from custom.dfci_swasth.constants import (
    CASE_TYPE_PATIENT,
    PROP_CCUSER_CASELOAD_CASE_ID,
    PROP_COUNSELLOR_CLOSED_CASE_LOAD,
    PROP_COUNSELLOR_LOAD,
)


def update_counsellor_load(patient_case, rule):
    num_related_updates = 0

    if patient_case.type != CASE_TYPE_PATIENT:
        return CaseRuleActionResult()

    ccuser_caseload_case = _get_ccuser_caseload_case(patient_case)

    # Updating the case type 'ccuser_caseload' case properties
    if ccuser_caseload_case:
        case_updates = _get_case_updates(ccuser_caseload_case)
        if case_updates:
            (submission, cases) = update_case(
                ccuser_caseload_case.domain,
                ccuser_caseload_case.case_id,
                case_properties=case_updates,
                xmlns=AUTO_UPDATE_XMLNS,
                device_id=__name__ + ".update_counsellor_load",
                form_name=rule.name,
            )
            num_related_updates = 1
            rule.log_submission(submission.form_id)

    return CaseRuleActionResult(
        num_related_updates=num_related_updates,
    )


def _get_ccuser_caseload_case(patient_case):
    case_id = patient_case.get_case_property(PROP_CCUSER_CASELOAD_CASE_ID)
    if case_id:
        try:
            return CommCareCase.objects.get_case(case_id, domain=patient_case.domain)
        except CaseNotFound:
            return None


def _get_case_updates(ccuser_caseload_case):
    counsellor_load = _get_updated_counsellor_load(ccuser_caseload_case)
    counsellor_closed_case_load = _get_updated_counsellor_closed_case_load(ccuser_caseload_case)

    result = {}
    # counsellor_load and counsellor_closed_case_load will always be present in the case
    # If not present for some scenario, update should be skipped for it
    if counsellor_load is not None:
        result.update({PROP_COUNSELLOR_LOAD: counsellor_load})
    if counsellor_closed_case_load is not None:
        result.update({PROP_COUNSELLOR_CLOSED_CASE_LOAD: counsellor_closed_case_load})
    return result


def _get_updated_counsellor_load(ccuser_caseload_case):
    counsellor_load = _get_integer_case_property_value(ccuser_caseload_case, PROP_COUNSELLOR_LOAD)
    if counsellor_load and counsellor_load >= 1:
        return counsellor_load - 1


def _get_updated_counsellor_closed_case_load(ccuser_caseload_case):
    counsellor_closed_case_load = _get_integer_case_property_value(
        ccuser_caseload_case, PROP_COUNSELLOR_CLOSED_CASE_LOAD)
    # increment counsellor_closed_case_load if its present and is at least 0
    # check for not None to avoid false negative for value 0
    if counsellor_closed_case_load is not None and counsellor_closed_case_load >= 0:
        return counsellor_closed_case_load + 1


def _get_integer_case_property_value(case, property_name):
    try:
        return int(case.get_case_property(property_name))
    except (TypeError, ValueError):
        return
