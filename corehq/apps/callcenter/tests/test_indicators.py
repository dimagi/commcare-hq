from corehq.apps.callcenter.indicator_sets import CallCenter, AAROHI_MOTHER_FORM
from corehq.apps.callcenter.utils import sync_user_cases
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.callcenter.tests.sql_fixture import load_data, load_custom_data
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

    @classmethod
    def tearDownClass(cls):
        cls.cc_domain.delete()
        cls.aarohi_domain.delete()

    def _test_indicators(self, domain, user, expected):
        indicator_set = CallCenter(domain, user)
        data = indicator_set.data
        self.assertIn(user.user_id, data)
        user_data = data[user.user_id]

        mismatches = []
        for k, v in expected.items():
            if user_data[k] != v:
                mismatches.append('{}: {} != {}'.format(k, v, user_data[k]))

        if mismatches:
            self.fail('Mismatching indicators:\n{}'.format('\t\n'.join(mismatches)))

    def test_callcenter_indicators(self):
        expected = {
            'formsSubmittedWeek0': 2L,
            'formsSubmittedWeek1': 4L,
            'formsSubmittedMonth0': 8L,
            'casesUpdatedMonth0': 2L,
            'casesUpdatedMonth1': 6L,
            'totalCases': 12L,
        }

        self._test_indicators(self.cc_domain, self.cc_user, expected)

    def test_custom_indicators(self):
        expected = {
            'formsSubmittedWeek0': 3L,
            'formsSubmittedWeek1': 3L,
            'formsSubmittedMonth0': 9L,
            'casesUpdatedMonth0': 0L,
            'casesUpdatedMonth1': 0L,
            'totalCases': 0L,
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

