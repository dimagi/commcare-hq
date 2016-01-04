from datetime import datetime, timedelta
from casexml.apps.case.mock import CaseFactory, CaseStructure
from casexml.apps.case.tests.util import delete_all_cases
from corehq.apps.app_manager.const import USERCASE_TYPE
from corehq.apps.callcenter.utils import (
    sync_call_center_user_case,
    is_midnight_for_domain,
    get_call_center_cases,
    DomainLite,
    sync_usercase,
)
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.hqcase.utils import get_case_by_domain_hq_user_id
from corehq.apps.users.models import CommCareUser
from django.test import TestCase, SimpleTestCase
from dimagi.utils.couch.undo import DELETED_SUFFIX

TEST_DOMAIN = 'cc_util_test'
CASE_TYPE = 'cc_flw'


class CallCenterUtilsTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.domain = create_domain(TEST_DOMAIN)
        user = CommCareUser.create(TEST_DOMAIN, 'user1', '***')
        cls.user_id = user.user_id

        cls.domain.call_center_config.enabled = True
        cls.domain.call_center_config.case_owner_id = user.user_id
        cls.domain.call_center_config.case_type = CASE_TYPE
        cls.domain.save()

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()

    def setUp(self):
        self.user = CommCareUser.get(self.user_id)

    def tearDown(self):
        delete_all_cases()

    def test_sync(self):
        sync_call_center_user_case(self.user)
        case = get_case_by_domain_hq_user_id(TEST_DOMAIN, self.user._id, CASE_TYPE)
        self.assertIsNotNone(case)
        self.assertEquals(case.name, self.user.username)
        self.assertEquals(case.username, self.user.raw_username)
        self.assertIsNotNone(case.language)
        self.assertIsNotNone(case.phone_number)

    def test_sync_full_name(self):
        name = 'Ricky Bowwood'
        self.user.set_full_name(name)
        sync_call_center_user_case(self.user)
        case = get_case_by_domain_hq_user_id(TEST_DOMAIN, self.user._id, CASE_TYPE)
        self.assertIsNotNone(case)
        self.assertEquals(case.name, name)

    def test_sync_inactive(self):
        sync_call_center_user_case(self.user)
        case = get_case_by_domain_hq_user_id(TEST_DOMAIN, self.user._id, CASE_TYPE)
        self.assertIsNotNone(case)

        self.user.is_active = False
        sync_call_center_user_case(self.user)
        case = get_case_by_domain_hq_user_id(TEST_DOMAIN, self.user._id, CASE_TYPE)
        self.assertTrue(case.closed)

    def test_sync_retired(self):
        sync_call_center_user_case(self.user)
        case = get_case_by_domain_hq_user_id(TEST_DOMAIN, self.user._id, CASE_TYPE)
        self.assertIsNotNone(case)

        self.user.base_doc += DELETED_SUFFIX
        sync_call_center_user_case(self.user)
        case = get_case_by_domain_hq_user_id(TEST_DOMAIN, self.user._id, CASE_TYPE)
        self.assertTrue(case.closed)

    def test_sync_update_update(self):
        sync_call_center_user_case(self.user)
        case = get_case_by_domain_hq_user_id(TEST_DOMAIN, self.user._id, CASE_TYPE)
        self.assertIsNotNone(case)
        self.assertEquals(case.name, self.user.username)

        name = 'Ricky Bowwood'
        self.user.set_full_name(name)
        sync_call_center_user_case(self.user)
        case = get_case_by_domain_hq_user_id(TEST_DOMAIN, self.user._id, CASE_TYPE)
        self.assertEquals(case.name, name)

    def test_sync_custom_user_data(self):
        self.user.user_data = {
            '': 'blank_key',
            'blank_val': '',
            'ok': 'good',
            'name with spaces': 'ok',
            '8starts_with_a_number': '0',
            'xml_starts_with_xml': '0',
            '._starts_with_punctuation': '0',
        }
        sync_call_center_user_case(self.user)
        case = get_case_by_domain_hq_user_id(TEST_DOMAIN, self.user._id, CASE_TYPE)
        self.assertIsNotNone(case)
        self.assertEquals(case.blank_val, '')
        self.assertEquals(case.ok, 'good')

    def test_get_call_center_cases_for_user(self):
        factory = CaseFactory(domain=TEST_DOMAIN, case_defaults={
            'user_id': self.user_id,
            'owner_id': self.user_id,
            'case_type': CASE_TYPE,
            'update': {'hq_user_id': self.user_id}
        })
        c1, c2, c3 = factory.create_or_update_cases([
            CaseStructure(attrs={'create': True}),
            CaseStructure(attrs={'create': True}),
            CaseStructure(attrs={'create': True, 'owner_id': 'another_user'}),
        ])
        cases = get_call_center_cases(TEST_DOMAIN, CASE_TYPE, self.user)
        self.assertEqual(len(cases), 2)
        case_ids = {case.case_id for case in cases}
        user_ids = {case.hq_user_id for case in cases}
        self.assertEqual(case_ids, set([c1.case_id, c2.case_id]))
        self.assertEqual(user_ids, set([self.user_id]))

    def test_get_call_center_cases_all(self):
        factory = CaseFactory(domain=TEST_DOMAIN, case_defaults={
            'user_id': self.user_id,
            'owner_id': self.user_id,
            'case_type': CASE_TYPE,
            'update': {'hq_user_id': self.user_id}
        })
        factory.create_or_update_cases([
            CaseStructure(attrs={'create': True}),
            CaseStructure(attrs={'create': True}),
            CaseStructure(attrs={'create': True, 'owner_id': 'another_user'}),
        ])
        cases = get_call_center_cases(TEST_DOMAIN, CASE_TYPE)
        self.assertEqual(len(cases), 3)

    def test_call_center_not_default_case_owner(self):
        """
        call center case owner should not change on sync
        """
        factory = CaseFactory(domain=TEST_DOMAIN, case_defaults={
            'user_id': self.user_id,
            'owner_id': 'another_user',
            'case_type': CASE_TYPE,
            'update': {'hq_user_id': self.user_id}
        })
        cases = factory.create_or_update_cases([
            CaseStructure(attrs={'create': True})
        ])
        sync_call_center_user_case(self.user)
        case = get_case_by_domain_hq_user_id(TEST_DOMAIN, self.user._id, CASE_TYPE)
        self.assertEqual(case.owner_id, cases[0].owner_id)


class CallCenterUtilsUserCaseTests(TestCase):

    def setUp(self):
        self.domain = create_domain(TEST_DOMAIN)
        self.domain.usercase_enabled = True
        self.domain.save()
        self.user = CommCareUser.create(TEST_DOMAIN, 'user1', '***', commit=False)  # Don't commit yet

    def tearDown(self):
        delete_all_cases()
        self.domain.delete()

    def test_sync_usercase_custom_user_data_on_create(self):
        """
        Custom user data should be synced when the user is created
        """
        self.user.user_data = {
            'completed_training': 'yes',
        }
        self.user.save()
        case = get_case_by_domain_hq_user_id(TEST_DOMAIN, self.user._id, USERCASE_TYPE)
        self.assertIsNotNone(case)
        self.assertEquals(case.completed_training, 'yes')

    def test_sync_usercase_custom_user_data_on_update(self):
        """
        Custom user data should be synced when the user is updated
        """
        self.user.user_data = {
            'completed_training': 'no',
        }
        self.user.save()
        self.user.user_data = {
            'completed_training': 'yes',
        }
        sync_usercase(self.user)
        case = get_case_by_domain_hq_user_id(TEST_DOMAIN, self.user._id, USERCASE_TYPE)
        self.assertEquals(case.completed_training, 'yes')

    def test_reactivate_user(self):
        """Confirm that reactivating a user re-opens its user case."""
        self.user.save()
        user_case = get_case_by_domain_hq_user_id(TEST_DOMAIN, self.user._id, USERCASE_TYPE)
        self.assertIsNotNone(user_case)

        self.user.is_active = False
        self.user.save()
        user_case = get_case_by_domain_hq_user_id(TEST_DOMAIN, self.user._id, USERCASE_TYPE)
        self.assertTrue(user_case.closed)

        self.user.is_active = True
        self.user.save()
        user_case = get_case_by_domain_hq_user_id(TEST_DOMAIN, self.user._id, USERCASE_TYPE)
        self.assertFalse(user_case.closed)

    def test_update_deactivated_user(self):
        """
        Confirm that updating a deactivated user also updates the user case.
        """
        self.user.save()
        user_case = get_case_by_domain_hq_user_id(TEST_DOMAIN, self.user._id, USERCASE_TYPE)
        self.assertIsNotNone(user_case)

        self.user.is_active = False
        self.user.save()
        user_case = get_case_by_domain_hq_user_id(TEST_DOMAIN, self.user._id, USERCASE_TYPE)
        self.assertTrue(user_case.closed)

        self.user.user_data = {'foo': 'bar'}
        self.user.save()
        user_case = get_case_by_domain_hq_user_id(TEST_DOMAIN, self.user._id, USERCASE_TYPE)
        self.assertTrue(user_case.closed)
        self.assertEquals(user_case.foo, 'bar')

    def test_update_and_reactivate_in_one_save(self):
        """
        Confirm that a usercase can be updated and reactived in a single save of the user model
        """
        """
        Confirm that updating a deactivated user also updates the user case.
        """
        self.user.save()
        user_case = get_case_by_domain_hq_user_id(TEST_DOMAIN, self.user._id, USERCASE_TYPE)
        self.assertIsNotNone(user_case)

        self.user.is_active = False
        self.user.save()
        user_case = get_case_by_domain_hq_user_id(TEST_DOMAIN, self.user._id, USERCASE_TYPE)
        self.assertTrue(user_case.closed)

        self.user.user_data = {'foo': 'bar'}
        self.user.is_active = True
        self.user.save()
        user_case = get_case_by_domain_hq_user_id(TEST_DOMAIN, self.user._id, USERCASE_TYPE)
        self.assertFalse(user_case.closed)
        self.assertEquals(user_case.foo, 'bar')

class DomainTimezoneTests(SimpleTestCase):
    def _test_midnights(self, utcnow, test_cases):
        for tz, offset, expected in test_cases:
            dom = DomainLite('', tz, '', True)
            self.assertEqual(dom.midnights(utcnow), expected, (tz, offset))

    def test_midnight_for_domain_general(self):
        utcnow = datetime(2015, 1, 1, 12, 0, 0)
        timezones = [
            ('Asia/Kolkata', 5.5, [datetime(2014, 12, 31, 18, 30), datetime(2015, 1, 1, 18, 30)]),
            ('UTC', 0, [datetime(2015, 1, 1, 0, 0), datetime(2015, 1, 2, 0, 0)]),
            ('Africa/Lagos', 1, [datetime(2014, 12, 31, 23, 0), datetime(2015, 1, 1, 23, 0)]),
            ('America/New_York', -5, [datetime(2015, 1, 1, 5, 0), datetime(2015, 1, 2, 5, 0)]),
            ('US/Eastern', -5, [datetime(2015, 1, 1, 5, 0), datetime(2015, 1, 2, 5, 0)]),
            ('Europe/London', 0, [datetime(2015, 1, 1, 0, 0), datetime(2015, 1, 2, 0, 0)]),
            ('Asia/Baghdad', 3, [datetime(2014, 12, 31, 21, 0), datetime(2015, 1, 1, 21, 0)]),
            ('America/Port-au-Prince', -5, [datetime(2015, 1, 1, 5, 0), datetime(2015, 1, 2, 5, 0)]),
            ('Africa/Porto-Novo', 1, [datetime(2014, 12, 31, 23, 0), datetime(2015, 1, 1, 23, 0)]),
            ('Africa/Nairobi', 3, [datetime(2014, 12, 31, 21, 0), datetime(2015, 1, 1, 21, 0)]),
            ('Asia/Anadyr', 12, [datetime(2014, 12, 31, 12, 0), datetime(2015, 1, 1, 12, 0)]),
            ('Pacific/Samoa', -11, [datetime(2015, 1, 1, 11, 0), datetime(2015, 1, 2, 11, 0)]),
        ]
        self._test_midnights(utcnow, timezones)

    def test_midnight_for_domain_cross_boundry(self):
        # Test crossing day boundry
        self._test_midnights(datetime(2015, 8, 27, 18, 30), [
            ('Asia/Kolkata', 5.5, [datetime(2015, 8, 26, 18, 30), datetime(2015, 8, 27, 18, 30)]),
        ])

        self._test_midnights(datetime(2015, 8, 27, 18, 31), [
            ('Asia/Kolkata', 5.5, [datetime(2015, 8, 27, 18, 30), datetime(2015, 8, 28, 18, 30)]),
        ])

    def test_midnight_for_domain_dst(self):
        # without DST
        self._test_midnights(datetime(2015, 1, 27, 11, 36), [
            ('US/Eastern', -5, [datetime(2015, 1, 27, 5, 0), datetime(2015, 1, 28, 5, 0)]),
        ])

        # with DST
        self._test_midnights(datetime(2015, 8, 27, 11, 36), [
            ('US/Eastern', -4, [datetime(2015, 8, 27, 4, 0), datetime(2015, 8, 28, 4, 0)]),
        ])

    def test_is_midnight_for_domain(self):
        midnight = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        midnights = [
            (midnight, True),
            (midnight + timedelta(minutes=10), True),
            (midnight + timedelta(minutes=20), False),
            (midnight - timedelta(minutes=1), False),
        ]
        for midnight_candidate, expected in midnights:
            is_midnight = is_midnight_for_domain(midnight, current_time=midnight_candidate)
            self.assertEqual(is_midnight, expected)
