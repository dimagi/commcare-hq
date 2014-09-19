from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.util import post_case_blocks
from casexml.apps.case.xml import V2
from corehq.apps.callcenter.indicator_sets import CallCenter, AAROHI_MOTHER_FORM, CallCenterV2
from corehq.apps.callcenter.utils import sync_user_cases
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.callcenter.tests.sql_fixture import load_data, load_custom_data
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.users.models import CommCareUser
from django.test import TestCase


def create_domain_and_user(domain_name, username):
    domain = create_domain(domain_name)
    user = CommCareUser.create(domain_name, username, '***')

    domain.call_center_config.enabled = True
    domain.call_center_config.case_owner_id = user.user_id
    domain.call_center_config.case_type = 'cc_flw'
    domain.save()

    sync_user_cases(user)
    return domain, user


class CallCenterTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cc_domain, cls.cc_user = create_domain_and_user('callcentertest', 'user1')
        load_data(cls.cc_domain.name, cls.cc_user.user_id)

        cls.aarohi_domain, cls.aarohi_user = create_domain_and_user('aarohi', 'user2')
        load_custom_data(cls.aarohi_domain.name, cls.aarohi_user.user_id, xmlns=AAROHI_MOTHER_FORM)

        # create one case of each type so that we get the indicators where there is no data for the period
        submit_case_blocks(
            CaseBlock(
                create=True,
                case_id='person1',
                case_type='person',
                user_id='user1',
                version=V2,
            ).as_string(), 'callcentertest')

        submit_case_blocks(
            CaseBlock(
                create=True,
                case_id='dog1',
                case_type='dog',
                user_id='user1',
                version=V2,
            ).as_string(), 'callcentertest')

    @classmethod
    def tearDownClass(cls):
        cls.cc_domain.delete()
        cls.aarohi_domain.delete()

    def _test_indicators(self, domain, user, expected):
        indicator_set = CallCenterV2(domain, user)
        data = indicator_set.get_data()
        self.assertIn(user.user_id, data)
        user_data = data[user.user_id]

        mismatches = []
        for k, v in expected.items():
            if user_data.get(k) != v:
                mismatches.append('{}: {} != {}'.format(k, v, user_data.get(k)))

        if mismatches:
            self.fail('Mismatching indicators:\n{}'.format('\t\n'.join(mismatches)))

    def test_callcenter_indicators(self):
        expected = {
            'formsSubmittedWeek0': 2L,
            'formsSubmittedWeek1': 4L,
            'formsSubmittedMonth0': 7L,
            'totalCases': 5L,

            'casesUpdatedWeek0': 0L,
            'casesUpdatedWeek1': 1L,
            'casesUpdatedMonth0': 3L,
            'casesUpdatedMonth1': 5L,

            'cases_total_week0': 4L,
            'cases_total_week1': 4L,
            'cases_total_month0': 6L,
            'cases_total_month1': 5L,
            'cases_total_person_week0': 1L,
            'cases_total_person_week1': 1L,
            'cases_total_person_month0': 3L,
            'cases_total_person_month1': 0L,
            'cases_total_dog_week0': 3L,
            'cases_total_dog_week1': 3L,
            'cases_total_dog_month0': 3L,
            'cases_total_dog_month1': 5L,

            'cases_opened_week0': 0L,
            'cases_opened_week1': 1L,
            'cases_opened_month0': 3L,
            'cases_opened_month1': 5L,
            'cases_opened_person_week0': 0L,
            'cases_opened_person_week1': 1L,
            'cases_opened_person_month0': 3L,
            'cases_opened_person_month1': 0L,
            'cases_opened_dog_week0': 0L,
            'cases_opened_dog_week1': 0L,
            'cases_opened_dog_month0': 0L,
            'cases_opened_dog_month1': 5L,

            'cases_closed_week0': 0L,
            'cases_closed_week1': 0L,
            'cases_closed_month0': 2L,
            'cases_closed_month1': 2L,
            'cases_closed_person_week0': 0L,
            'cases_closed_person_week1': 0L,
            'cases_closed_person_month0': 2L,
            'cases_closed_person_month1': 0L,
            'cases_closed_dog_week0': 0L,
            'cases_closed_dog_week1': 0L,
            'cases_closed_dog_month0': 0L,
            'cases_closed_dog_month1': 2L,
            
            'cases_active_week0': 0L,
            'cases_active_week1': 1L,
            'cases_active_month0': 3L,
            'cases_active_month1': 5L,
            'cases_active_person_week0': 0L,
            'cases_active_person_week1': 1L,
            'cases_active_person_month0': 3L,
            'cases_active_person_month1': 0L,
            'cases_active_dog_week0': 0L,
            'cases_active_dog_week1': 0L,
            'cases_active_dog_month0': 0L,
            'cases_active_dog_month1': 5L,
        }

        self._test_indicators(self.cc_domain, self.cc_user, expected)

    def test_custom_indicators(self):
        expected = {
            'formsSubmittedWeek0': 3L,
            'formsSubmittedWeek1': 3L,
            'formsSubmittedMonth0': 9L,
            # 'casesUpdatedMonth0': 0L,
            # 'casesUpdatedMonth1': 0L,
            'totalCases': 0L,
            'cases_total_week0': 0L,
            'cases_total_week1': 0L,
            'cases_total_month0': 0L,
            'cases_total_month1': 0L,
            'motherFormsWeek0': 3L,
            'motherFormsWeek1': 3L,
            'motherFormsMonth0': 9L,
            'childFormsWeek0': 0L,
            'childFormsWeek1': 0L,
            'childFormsMonth0': 0L,
            'motherDurationWeek0': 3L,
            'motherDurationWeek1': 4L,
            'motherDurationMonth0': 4L,
        }

        self._test_indicators(self.aarohi_domain, self.aarohi_user, expected)

