from corehq.apps.callcenter.indicator_sets import CallCenter
from corehq.apps.callcenter.utils import sync_user_cases
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.callcenter.tests.sql_fixture import load_data
from corehq.apps.hqcase.utils import get_case_by_domain_hq_user_id
from corehq.apps.users.models import CommCareUser
from django.test import TestCase


class CallCenterTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cc_domain = create_domain('callcentertest')

        cls.cc_user = CommCareUser.create('callcentertest', 'user1', '***')

        cls.cc_domain.call_center_config.enabled = True
        cls.cc_domain.call_center_config.case_owner_id = cls.cc_user.user_id
        cls.cc_domain.call_center_config.case_type = 'cc_flw'
        cls.cc_domain.save()

        sync_user_cases(cls.cc_user)

        cls.cc_user_caseid = get_case_by_domain_hq_user_id(cls.cc_domain.name, cls.cc_user.user_id)['id']

        # cls.aarohi_domain = create_domain('aarohi')
        # cls.aarohi_user = CommCareUser.create('aarohi', 'user2', '***')

        load_data(cls.cc_domain.name, cls.cc_user.user_id)

    @classmethod
    def tearDownClass(cls):
        pass
        # cls.cc_domain.delete()
        # cls.cc_user.delete()

    def test_callcenter_group(self):
        indicator_set = CallCenter(self.cc_domain, self.cc_user)
        data = indicator_set.data
        self.assertIn(self.cc_user.user_id, data)
        user_data = data[self.cc_user.user_id]
        self.assertEqual(user_data['formsSubmittedWeek0'], 2L)
        self.assertEqual(user_data['formsSubmittedWeek1'], 4L)
        self.assertEqual(user_data['formsSubmittedMonth0'], 7L)
        self.assertEqual(user_data['casesUpdatedMonth0'], 2L)
        self.assertEqual(user_data['casesUpdatedMonth1'], 5L)
        self.assertEqual(user_data['totalCases'], 12L)

