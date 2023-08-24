from datetime import datetime

from corehq.apps.data_interfaces.models import CaseRuleActionResult
from corehq.apps.hqcase.utils import update_case, AUTO_UPDATE_XMLNS
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.models import CommCareCase
from custom.dfci_swasth.constants import (
    CASE_TYPE_PATIENT,
    PROP_SCREENING_EXP_DATE,
    PROP_COUNSELLING_EXP_DATE,
    PROP_CCUSER_CASELOAD_CASE_ID,
    PROP_COUNSELLOR_LOAD,
)
from dimagi.utils.parsing import ISO_DATE_FORMAT


def update_counsellor_load(patient_case, rule):
    num_related_updates = 0

    if patient_case.type != CASE_TYPE_PATIENT:
        return CaseRuleActionResult(num_related_updates=num_related_updates)

    screening_expiry_date = _get_property_date_object(patient_case, PROP_SCREENING_EXP_DATE)
    if not screening_expiry_date:
        return CaseRuleActionResult(num_related_updates=num_related_updates)

    counselling_expiry_date = _get_property_date_object(patient_case, PROP_COUNSELLING_EXP_DATE)

    if not counselling_expiry_date:
        counselling_expiry_date = datetime.max

    today_date = datetime.now()
    if screening_expiry_date > today_date and counselling_expiry_date > today_date:
        return CaseRuleActionResult()

    ccuser_caseload_case = _get_ccuser_caseload_case(patient_case)

    # Updating the case type 'ccuser_caseload' case properties
    if ccuser_caseload_case:
        case_updates = _get_case_updates(ccuser_caseload_case)
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


def _get_property_date_object(patient_case, property_name):
    screening_expiry_date = patient_case.get_case_property(property_name)
    if screening_expiry_date:
        try:
            return datetime.strptime(screening_expiry_date, ISO_DATE_FORMAT)
        except ValueError:
            return None


def _get_case_updates(ccuser_caseload_case):
    try:
        return {PROP_COUNSELLOR_LOAD: _get_updated_counsellor_load(ccuser_caseload_case)}
    except (TypeError, ValueError):
        return {}


def _get_updated_counsellor_load(ccuser_caseload_case):
    counsellor_load = int(ccuser_caseload_case.get_case_property(PROP_COUNSELLOR_LOAD))
    return counsellor_load - 1
