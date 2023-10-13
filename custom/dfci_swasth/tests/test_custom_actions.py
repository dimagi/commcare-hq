from casexml.apps.case.mock import CaseFactory
from corehq.apps.data_interfaces.models import AutomaticUpdateRule
from corehq.apps.data_interfaces.tests.test_auto_case_updates import BaseCaseRuleTest
from corehq.apps.data_interfaces.tests.util import create_empty_rule
from corehq.apps.domain.shortcuts import create_domain
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from custom.dfci_swasth.constants import (
    CASE_TYPE_PATIENT,
    CASE_TYPE_CASELOAD,
    PROP_CCUSER_CASELOAD_CASE_ID,
    PROP_COUNSELLOR_LOAD,
    PROP_COUNSELLOR_CLOSED_CASE_LOAD,
)
from custom.dfci_swasth.rules.custom_actions import update_counsellor_load


class UpdateCounsellorPropertiesTest(BaseCaseRuleTest):
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

    def test_case_update_not_successful_ccuser_caseload_case_missing(self):
        patient_case = CaseFactory(self.domain).create_case(
            case_type=CASE_TYPE_PATIENT,
            update={PROP_CCUSER_CASELOAD_CASE_ID: "random_id"},
        )

        result = update_counsellor_load(patient_case, self.patient_rule)

        self.assertEqual(0, result.num_related_updates)

    def test_case_update_not_successful_ccuser_caseload_property_missing(self):
        patient_case = CaseFactory(self.domain).create_case(
            case_type=CASE_TYPE_PATIENT,
        )

        result = update_counsellor_load(patient_case, self.patient_rule)

        self.assertEqual(0, result.num_related_updates)

    def test_case_update_not_successful_when_both_properties_non_numeric(self):
        _, patient_case = self._create_cases('abc', 'xyz')

        result = update_counsellor_load(patient_case, self.patient_rule)

        self.assertEqual(0, result.num_related_updates)

    def test_case_update_not_successful_when_both_properties_invalid(self):
        _, patient_case = self._create_cases(0, -1)

        result = update_counsellor_load(patient_case, self.patient_rule)

        self.assertEqual(0, result.num_related_updates)

    def test_case_update_successful_ccuser_caseload_case_present(self):
        _, patient_case = self._create_cases(10, 0)

        result = update_counsellor_load(patient_case, self.patient_rule)

        self.assertEqual(1, result.num_related_updates)

    def test_case_update_successful_when_only_case_load_non_numeric(self):
        _, patient_case = self._create_cases('abc', 0)

        result = update_counsellor_load(patient_case, self.patient_rule)

        self.assertEqual(1, result.num_related_updates)

    def test_case_update_successful_when_only_coun_closed_case_load_non_numeric(self):
        _, patient_case = self._create_cases(1, 'abc')

        result = update_counsellor_load(patient_case, self.patient_rule)

        self.assertEqual(1, result.num_related_updates)

    def _create_cases(self, counsellor_load, counsellor_closed_case_load):
        ccuser_caseload_case = CaseFactory(self.domain).create_case(
            case_type=CASE_TYPE_CASELOAD,
            update={
                PROP_COUNSELLOR_LOAD: counsellor_load,
                PROP_COUNSELLOR_CLOSED_CASE_LOAD: counsellor_closed_case_load,
            },
        )

        case_data = {PROP_CCUSER_CASELOAD_CASE_ID: ccuser_caseload_case.case_id}

        patient_case = CaseFactory(self.domain).create_case(
            case_type=CASE_TYPE_PATIENT,
            update=case_data,
        )

        return ccuser_caseload_case, patient_case
