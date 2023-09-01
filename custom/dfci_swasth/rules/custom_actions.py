from corehq.apps.data_interfaces.models import CaseRuleActionResult
from corehq.apps.hqcase.utils import update_case, AUTO_UPDATE_XMLNS
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.models import CommCareCase
from custom.dfci_swasth.constants import (
    CASE_TYPE_PATIENT,
    PROP_CCUSER_CASELOAD_CASE_ID,
    PROP_COUNSELLOR_LOAD,
)


def update_counsellor_load(patient_case, rule):
    num_related_updates = 0

    if patient_case.type != CASE_TYPE_PATIENT:
        return CaseRuleActionResult(num_related_updates=num_related_updates)

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
    coun_ccuser_caseload_case_id = patient_case.get_case_property(PROP_CCUSER_CASELOAD_CASE_ID)
    if coun_ccuser_caseload_case_id:
        try:
            return CommCareCase.objects.get_case(coun_ccuser_caseload_case_id, domain=patient_case.domain)
        except CaseNotFound:
            return None


def _get_case_updates(ccuser_caseload_case):
    counsellor_load = _get_updated_counsellor_load(ccuser_caseload_case)
    if not counsellor_load:
        return {}
    return {PROP_COUNSELLOR_LOAD: counsellor_load}


def _get_updated_counsellor_load(ccuser_caseload_case):
    try:
        counsellor_load_raw = ccuser_caseload_case.get_case_property(PROP_COUNSELLOR_LOAD)
        if counsellor_load_raw is None:
            return
        counsellor_load = int(counsellor_load_raw)
        # Value of counsellor load can be minimum 0
        if counsellor_load >= 1:
            return counsellor_load - 1
    except (TypeError, ValueError):
        return
