from datetime import datetime, timedelta

from casexml.apps.case.mock import CaseFactory
from corehq.apps.data_interfaces.models import AutomaticUpdateRule
from corehq.apps.data_interfaces.tests.test_auto_case_updates import BaseCaseRuleTest
from corehq.apps.data_interfaces.tests.util import create_empty_rule
from corehq.apps.domain.shortcuts import create_domain
from corehq.form_processor.models import CommCareCase
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from custom.dfci_swasth.constants import (
    CASE_TYPE_PATIENT,
    CASE_TYPE_CASELOAD,
    PROP_CCUSER_CASELOAD_CASE_ID,
    PROP_COUNSELLOR_LOAD,
    PROP_SCREENING_EXP_DATE,
    PROP_COUNSELLING_EXP_DATE,
)
from custom.dfci_swasth.rules.custom_actions import update_counsellor_load
from dimagi.utils.parsing import ISO_DATE_FORMAT


class UpdateCounsellorLoadTest(BaseCaseRuleTest):
    domain = 'dfci-swasth'

    def setUp(self):
        super().setUp()
        self.domain_obj = create_domain(self.domain)
        self.patient_rule = create_empty_rule(
            self.domain, AutomaticUpdateRule.WORKFLOW_CASE_UPDATE, case_type=CASE_TYPE_PATIENT,
        )

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases()
        super().tearDown()

    def test_non_patient_case(self):
        patient_case = CaseFactory(self.domain).create_case(
            case_type="non-patient",
        )

        result = update_counsellor_load(patient_case, self.patient_rule)
        self.assertEqual(0, result.num_related_updates)

    def test_case_update_successful_no_counselling_date(self):
        ccuser_caseload_case, patient_case = self._create_cases(
            counsellor_load=10,
            screening_expiry_date=(datetime.now() + timedelta(days=-1)).strftime(ISO_DATE_FORMAT),
        )

        result = update_counsellor_load(patient_case, self.patient_rule)

        self.assertEqual(1, result.num_related_updates)

        case1 = CommCareCase.objects.get_case(ccuser_caseload_case.case_id)
        self.assertEqual(9, int(case1.get_case_property(PROP_COUNSELLOR_LOAD)))

    def test_case_update_successful_with_counselling_date(self):
        ccuser_caseload_case, patient_case = self._create_cases(
            counsellor_load=10,
            screening_expiry_date=(datetime.now() + timedelta(days=-2)).strftime(ISO_DATE_FORMAT),
            counselling_expiry_date=(datetime.now() + timedelta(days=-1)).strftime(ISO_DATE_FORMAT),
        )

        result = update_counsellor_load(patient_case, self.patient_rule)

        self.assertEqual(1, result.num_related_updates)

        case1 = CommCareCase.objects.get_case(ccuser_caseload_case.case_id)
        self.assertEqual(9, int(case1.get_case_property(PROP_COUNSELLOR_LOAD)))

    def test_case_update_not_successful_expiry_time_diff(self):
        ccuser_caseload_case, patient_case = self._create_cases(
            counsellor_load=10,
            screening_expiry_date=(datetime.now() + timedelta(days=1)).strftime(ISO_DATE_FORMAT),
            counselling_expiry_date=(datetime.now() + timedelta(days=2)).strftime(ISO_DATE_FORMAT),
        )

        result = update_counsellor_load(patient_case, self.patient_rule)

        self.assertEqual(0, result.num_related_updates)

        case1 = CommCareCase.objects.get_case(ccuser_caseload_case.case_id)
        self.assertEqual(10, int(case1.get_case_property(PROP_COUNSELLOR_LOAD)))
        self.assertFalse(case1.closed)

    def test_case_update_not_successful_screening_expiry_date_missing(self):
        ccuser_caseload_case, patient_case = self._create_cases(
            counsellor_load=10,
            counselling_expiry_date=(datetime.now() + timedelta(days=2)).strftime(ISO_DATE_FORMAT),
        )

        result = update_counsellor_load(patient_case, self.patient_rule)

        self.assertEqual(0, result.num_related_updates)

        case1 = CommCareCase.objects.get_case(ccuser_caseload_case.case_id)
        self.assertEqual(10, int(case1.get_case_property(PROP_COUNSELLOR_LOAD)))
        self.assertFalse(case1.closed)

    def test_case_update_not_successful_ccuser_caseload_case_missing(self):
        patient_case = CaseFactory(self.domain).create_case(
            case_type=CASE_TYPE_PATIENT,
            update={PROP_SCREENING_EXP_DATE: "2000-11-11",
                    PROP_CCUSER_CASELOAD_CASE_ID: "random_id"},
        )

        result = update_counsellor_load(patient_case, self.patient_rule)

        self.assertEqual(0, result.num_related_updates)

    def _create_cases(self, counsellor_load, screening_expiry_date=None, counselling_expiry_date=None):
        ccuser_caseload_case = CaseFactory(self.domain).create_case(
            case_type=CASE_TYPE_CASELOAD,
            update={
                PROP_COUNSELLOR_LOAD: counsellor_load,
            },
        )

        case_data = {PROP_CCUSER_CASELOAD_CASE_ID: ccuser_caseload_case.case_id}

        if screening_expiry_date:
            case_data.update({PROP_SCREENING_EXP_DATE: screening_expiry_date})

        if counselling_expiry_date:
            case_data.update({PROP_COUNSELLING_EXP_DATE: counselling_expiry_date})

        patient_case = CaseFactory(self.domain).create_case(
            case_type=CASE_TYPE_PATIENT,
            update=case_data,
        )

        return ccuser_caseload_case, patient_case
