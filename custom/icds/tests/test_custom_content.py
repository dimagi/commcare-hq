from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.apps.hqcase.utils import update_case
from corehq.apps.locations.tests.util import make_loc, setup_location_types
from corehq.apps.users.models import CommCareUser
from corehq.messaging.scheduling.models import CustomContent
from corehq.messaging.scheduling.scheduling_partitioned.models import CaseTimedScheduleInstance
from custom.icds.const import (
    AWC_LOCATION_TYPE_CODE,
    SUPERVISOR_LOCATION_TYPE_CODE,
    BLOCK_LOCATION_TYPE_CODE,
    DISTRICT_LOCATION_TYPE_CODE,
    STATE_TYPE_CODE,
    ANDHRA_PRADESH_SITE_CODE,
    MAHARASHTRA_SITE_CODE,
    ENGLISH,
    HINDI,
    TELUGU,
    MARATHI,
)
from custom.icds.messaging.custom_content import (
    GROWTH_MONITORING_XMLNS,
    get_state_code,
    get_language_code_for_state,
    render_message,
)
from custom.icds.tests.base import BaseICDSTest
from mock import patch


TEST_GROWTH_FORM_XML = """<?xml version="1.0" ?>
<data xmlns="{xmlns}">
    <weight_prev>{weight_prev}</weight_prev>
    <weight_child>{weight_child}</weight_child>
    <case case_id="{case_id}" xmlns="http://commcarehq.org/case/transaction/v2">
        <update>
            <weight_child>{weight_child}</weight_child>
        </update>
    </case>
</data>
"""


def submit_growth_form(domain, case_id, weight_prev, weight_child):
    xml = TEST_GROWTH_FORM_XML.format(
        xmlns=GROWTH_MONITORING_XMLNS,
        case_id=case_id,
        weight_prev=weight_prev,
        weight_child=weight_child,
    )
    submit_form_locally(xml, domain)


class CustomContentTest(BaseICDSTest):
    domain = 'icds-custom-content-test'

    @classmethod
    def setUpClass(cls):
        super(CustomContentTest, cls).setUpClass()

        cls.location_types = setup_location_types(cls.domain, [
            STATE_TYPE_CODE,
            DISTRICT_LOCATION_TYPE_CODE,
            BLOCK_LOCATION_TYPE_CODE,
            SUPERVISOR_LOCATION_TYPE_CODE,
            AWC_LOCATION_TYPE_CODE,
        ])

        cls.state1 = make_loc('state1', domain=cls.domain, type=STATE_TYPE_CODE)
        cls.district1 = make_loc('district1', domain=cls.domain, type=DISTRICT_LOCATION_TYPE_CODE,
            parent=cls.state1)
        cls.block1 = make_loc('block1', domain=cls.domain, type=BLOCK_LOCATION_TYPE_CODE, parent=cls.district1)
        cls.ls1 = make_loc('ls1', domain=cls.domain, type=SUPERVISOR_LOCATION_TYPE_CODE, parent=cls.block1)
        cls.awc1 = make_loc('awc1', domain=cls.domain, type=AWC_LOCATION_TYPE_CODE, parent=cls.ls1)
        cls.awc2 = make_loc('awc2', domain=cls.domain, type=AWC_LOCATION_TYPE_CODE, parent=None)

        cls.user1 = CommCareUser.create(cls.domain, 'mobile-1', 'abc', location=cls.awc1)
        cls.user2 = CommCareUser.create(cls.domain, 'mobile-2', 'abc', location=cls.awc2)
        cls.user3 = CommCareUser.create(cls.domain, 'mobile-3', 'abc', location=cls.ls1)

        cls.create_basic_related_cases(cls.awc1.location_id)
        cls.red_child_health_case = cls.create_case(
            'child_health',
            parent_case_id=cls.child_person_case.case_id,
            parent_identifier='parent',
            parent_relationship='extension',
            update={'zscore_grading_wfa': 'red'},
            owner_id=cls.awc1.location_id,
        )

    def test_static_negative_growth_indicator(self):
        c = CustomContent(custom_content_id='ICDS_STATIC_NEGATIVE_GROWTH_MESSAGE')

        schedule_instance = CaseTimedScheduleInstance(
            domain=self.domain,
            case_id=self.child_health_case.case_id,
        )

        # Test when current weight is greater than previous
        submit_growth_form(self.domain, self.child_health_case.case_id, '10.1', '10.4')
        self.assertEqual(
            c.get_list_of_messages(self.mother_person_case, schedule_instance),
            []
        )

        # Test when current weight is equal to previous
        submit_growth_form(self.domain, self.child_health_case.case_id, '10.1', '10.1')
        self.assertEqual(
            c.get_list_of_messages(self.mother_person_case, schedule_instance),
            ["As per the latest records of your AWC, the weight of your child Joe has remained static in the last "
             "month. Please consult your AWW for necessary advice."]
        )

        # Test when current weight is less than previous
        submit_growth_form(self.domain, self.child_health_case.case_id, '10.1', '9.9')
        self.assertEqual(
            c.get_list_of_messages(self.mother_person_case, schedule_instance),
            ["As per the latest records of your AWC, the weight of your child Joe has reduced in the last month. "
             "Please consult your AWW for necessary advice."]
        )

        # Test ignoring forms with the wrong xmlns
        update_case(self.domain, self.child_health_case.case_id, {'property': 'value1'})
        update_case(self.domain, self.child_health_case.case_id, {'property': 'value2'})
        update_case(self.domain, self.child_health_case.case_id, {'property': 'value3'})
        update_case(self.domain, self.child_health_case.case_id, {'property': 'value4'})
        update_case(self.domain, self.child_health_case.case_id, {'property': 'value5'})
        update_case(self.domain, self.child_health_case.case_id, {'property': 'value6'})
        update_case(self.domain, self.child_health_case.case_id, {'property': 'value7'})
        update_case(self.domain, self.child_health_case.case_id, {'property': 'value8'})
        update_case(self.domain, self.child_health_case.case_id, {'property': 'value9'})
        update_case(self.domain, self.child_health_case.case_id, {'property': 'value10'})

        self.assertEqual(
            c.get_list_of_messages(self.mother_person_case, schedule_instance),
            ["As per the latest records of your AWC, the weight of your child Joe has reduced in the last month. "
             "Please consult your AWW for necessary advice."]
        )

    def test_static_negative_growth_indicator_with_red_status(self):
        c = CustomContent(custom_content_id='ICDS_STATIC_NEGATIVE_GROWTH_MESSAGE')

        schedule_instance = CaseTimedScheduleInstance(
            domain=self.domain,
            case_id=self.red_child_health_case.case_id,
        )

        # Current weight is less than previous, but grade is red, so no messages are sent
        submit_growth_form(self.domain, self.red_child_health_case.case_id, '10.1', '9.9')
        self.assertEqual(
            c.get_list_of_messages(self.mother_person_case, schedule_instance),
            []
        )

    @patch('custom.icds.messaging.custom_content.get_language_code_for_state')
    def test_missed_cf_visit_to_aww(self, language_code_patch):
        c = CustomContent(custom_content_id='ICDS_MISSED_CF_VISIT_TO_AWW')

        schedule_instance = CaseTimedScheduleInstance(
            domain=self.domain,
            case_id=self.ccs_record_case.case_id,
        )

        language_code_patch.return_value = ENGLISH
        self.assertEqual(
            c.get_list_of_messages(self.user1, schedule_instance),
            ["AWC awc1 has not reported a visit during complementary feeding initiation period for Sam"],
        )

    @patch('custom.icds.messaging.custom_content.get_language_code_for_state')
    def test_missed_cf_visit_to_ls(self, language_code_patch):
        c = CustomContent(custom_content_id='ICDS_MISSED_CF_VISIT_TO_LS')

        schedule_instance = CaseTimedScheduleInstance(
            domain=self.domain,
            case_id=self.ccs_record_case.case_id,
        )

        language_code_patch.return_value = ENGLISH
        self.assertEqual(
            c.get_list_of_messages(self.user3, schedule_instance),
            ["AWC awc1 has not reported a visit during complementary feeding initiation period for Sam"],
        )

    @patch('custom.icds.messaging.custom_content.get_language_code_for_state')
    def test_missed_pnc_visit_to_ls(self, language_code_patch):
        c = CustomContent(custom_content_id='ICDS_MISSED_PNC_VISIT_TO_LS')

        schedule_instance = CaseTimedScheduleInstance(
            domain=self.domain,
            case_id=self.ccs_record_case.case_id,
        )

        language_code_patch.return_value = ENGLISH
        self.assertEqual(
            c.get_list_of_messages(self.user3, schedule_instance),
            ["AWC awc1 has not reported a visit during the PNC within one week of delivery for Sam"],
        )

    @patch('custom.icds.messaging.custom_content.get_language_code_for_state')
    def test_child_illness_reported(self, language_code_patch):
        c = CustomContent(custom_content_id='ICDS_CHILD_ILLNESS_REPORTED')

        schedule_instance = CaseTimedScheduleInstance(
            domain=self.domain,
            case_id=self.child_person_case.case_id,
        )

        language_code_patch.return_value = ENGLISH
        self.assertEqual(
            c.get_list_of_messages(self.user3, schedule_instance),
            ["AWC awc1 has reported illness for the child Joe. Please ensure that AWW follows up with mother "
             "immediately"],
        )

    @patch('custom.icds.messaging.custom_content.get_language_code_for_state')
    def test_cf_visits_complete(self, language_code_patch):
        c = CustomContent(custom_content_id='ICDS_CF_VISITS_COMPLETE')

        schedule_instance = CaseTimedScheduleInstance(
            domain=self.domain,
            case_id=self.ccs_record_case.case_id,
        )

        language_code_patch.return_value = ENGLISH
        self.assertEqual(
            c.get_list_of_messages(self.user1, schedule_instance),
            ["Congratulations! You've done all the Complementary Feeding  Visits for Sam"],
        )

    @patch('custom.icds.messaging.custom_content.get_language_code_for_state')
    def test_child_vaccinations_complete(self, language_code_patch):
        c = CustomContent(custom_content_id='ICDS_CHILD_VACCINATIONS_COMPLETE')

        schedule_instance = CaseTimedScheduleInstance(
            domain=self.domain,
            case_id=self.child_tasks_case.case_id,
        )

        language_code_patch.return_value = ENGLISH
        self.assertEqual(
            c.get_list_of_messages(self.user1, schedule_instance),
            ["Congratulations! You've given all the vaccines to Joe"],
        )

    def test_get_state_code(self):
        self.assertEqual(get_state_code(self.user1.location), 'state1')
        self.assertIsNone(get_state_code(self.user2.location))
        self.assertEqual(get_state_code(self.user3.location), 'state1')

    def test_get_language_code_for_state(self):
        self.assertEqual(get_language_code_for_state(ANDHRA_PRADESH_SITE_CODE), TELUGU)
        self.assertEqual(get_language_code_for_state(MAHARASHTRA_SITE_CODE), MARATHI)
        self.assertEqual(get_language_code_for_state(None), HINDI)

    def test_render_message(self):
        context = {
            'awc': '0000',
            'beneficiary': 'Sam',
        }
        self.assertEqual(
            render_message(ENGLISH, 'missed_cf_visit_to_aww.txt', context),
            "AWC 0000 has not reported a visit during complementary feeding initiation period for Sam"
        )
