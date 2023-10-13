from datetime import datetime

from casexml.apps.case.mock import CaseFactory
from dimagi.utils.parsing import ISO_DATE_FORMAT

from corehq.apps.app_manager.const import USERCASE_TYPE
from corehq.apps.app_manager.util import enable_usercase
from corehq.apps.callcenter.sync_usercase import sync_usercases
from corehq.apps.data_interfaces.models import AutomaticUpdateRule
from corehq.apps.data_interfaces.tests.test_auto_case_updates import (
    BaseCaseRuleTest,
)
from corehq.apps.data_interfaces.tests.util import create_empty_rule
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es.case_search import case_search_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.apps.users.dbaccessors import delete_all_users
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.util import normalize_username
from corehq.form_processor.models import CommCareCase
from corehq.form_processor.tests.utils import FormProcessorTestUtils, sharded
from custom.covid.rules.custom_actions import (
    close_cases_assigned_to_checkin,
    set_all_activity_complete_date_to_today,
)
from custom.covid.rules.custom_criteria import associated_usercase_closed


@sharded
@es_test(requires=[case_search_adapter])
class DeactivatedMobileWorkersTest(BaseCaseRuleTest):
    def setUp(self):
        super().setUp()
        delete_all_users()

        self.domain_obj = create_domain(self.domain)
        enable_usercase(self.domain)

        username = normalize_username("mobile_worker_1", self.domain)
        self.mobile_worker = CommCareUser.create(self.domain, username, "123", None, None)
        sync_usercases(self.mobile_worker, self.domain)

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases()
        delete_all_users()
        super().tearDown()

    def make_checkin_case(self, properties=None):
        properties = properties if properties is not None else {"username": self.mobile_worker.raw_username}
        checkin_case = CaseFactory(self.domain).create_case(
            case_type="checkin",
            owner_id=self.mobile_worker.get_id,
            update=properties,
        )

        case_search_adapter.index(checkin_case, refresh=True)
        return checkin_case

    def close_all_usercases(self):
        usercase_ids = CommCareCase.objects.get_case_ids_in_domain(self.domain, USERCASE_TYPE)
        for usercase_id in usercase_ids:
            CaseFactory(self.domain).close_case(usercase_id)
            usercase = CommCareCase.objects.get_case(usercase_id, self.domain)

            case_search_adapter.index(
                usercase,
                refresh=True
            )

    def test_associated_usercase_closed(self):
        checkin_case = self.make_checkin_case()
        self.close_all_usercases()
        self.assertTrue(associated_usercase_closed(checkin_case, None))

    def test_checkin_case_no_username_skipped(self):
        checkin_case = self.make_checkin_case(properties={})
        self.close_all_usercases()
        self.assertFalse(associated_usercase_closed(checkin_case, None))

    def test_custom_action(self):
        checkin_case = self.make_checkin_case()
        rule = create_empty_rule(
            self.domain, AutomaticUpdateRule.WORKFLOW_CASE_UPDATE, case_type="checkin",
        )
        case_properties = {
            "assigned_to_primary_checkin_case_id": checkin_case.case_id,
            "is_assigned_primary": "foo",
            "assigned_to_primary_name": "bar",
            "assigned_to_primary_username": "baz",
        }
        patient_case = CaseFactory(self.domain).create_case(
            case_type="patient", owner_id=self.mobile_worker.get_id, update=case_properties,
        )
        other_patient_case = CaseFactory(self.domain).create_case(
            case_type="patient",
            owner_id=self.mobile_worker.get_id,
            update={"assigned_to_primary_checkin_case_id": "123"},
        )
        other_case = CaseFactory(self.domain).create_case(
            case_type="other",
            owner_id=self.mobile_worker.get_id,
            update={"assigned_to_primary_checkin_case_id": checkin_case.case_id},
        )
        for case in [patient_case, other_patient_case, other_case]:
            case_search_adapter.index(
                case,
                refresh=True
            )

        close_cases_assigned_to_checkin(checkin_case, rule)

        self.assertTrue(CommCareCase.objects.get_case(checkin_case.case_id).closed, self.domain)

        patient_case = CommCareCase.objects.get_case(patient_case.case_id, self.domain)
        self.assertFalse(patient_case.closed)
        for prop in case_properties:
            self.assertEqual(patient_case.get_case_property(prop), "")

        other_case = CommCareCase.objects.get_case(other_case.case_id, self.domain)
        self.assertFalse(other_case.closed)
        self.assertEqual(
            other_case.get_case_property("assigned_to_primary_checkin_case_id"),
            checkin_case.case_id,
        )

        other_patient_case = CommCareCase.objects.get_case(other_patient_case.case_id, self.domain)
        self.assertFalse(other_patient_case.closed)
        self.assertEqual(
            other_patient_case.get_case_property("assigned_to_primary_checkin_case_id"), "123",
        )


class AllActivityCompleteDateTest(BaseCaseRuleTest):
    def setUp(self):
        super().setUp()
        self.domain_obj = create_domain(self.domain)

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases()
        super().tearDown()

    def test_custom_action(self):
        rule = create_empty_rule(
            self.domain, AutomaticUpdateRule.WORKFLOW_CASE_UPDATE, case_type="circus",
        )

        case1 = CaseFactory(self.domain).create_case(
            case_type="circus",
            update={
                "all_activity_complete_date": "2021-06-31",
            },
        )
        case2 = CaseFactory(self.domain).create_case(
            case_type="circus",
            update={
                "size": "big",
            },
        )

        set_all_activity_complete_date_to_today(case1, rule)
        set_all_activity_complete_date_to_today(case2, rule)

        today = datetime.today().strftime(ISO_DATE_FORMAT)
        case1 = CommCareCase.objects.get_case(case1.case_id)
        case2 = CommCareCase.objects.get_case(case2.case_id)
        self.assertEqual(case1.get_case_property("all_activity_complete_date"), "2021-06-31")
        self.assertEqual(case2.get_case_property("all_activity_complete_date"), today)
        self.assertFalse(case1.closed)
        self.assertFalse(case2.closed)
