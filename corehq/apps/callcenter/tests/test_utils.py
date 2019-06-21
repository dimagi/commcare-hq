from __future__ import absolute_import
from __future__ import unicode_literals
import mock
import uuid
from datetime import datetime, timedelta
from casexml.apps.case.mock import CaseFactory, CaseStructure
from casexml.apps.case.tests.util import delete_all_cases
from casexml.apps.case.xform import get_case_updates
from corehq.apps.app_manager.const import USERCASE_TYPE
from corehq.apps.callcenter.const import CALLCENTER_USER
from corehq.apps.callcenter.sync_user_case import sync_call_center_user_case, sync_usercase
from corehq.apps.callcenter.utils import (
    is_midnight_for_domain,
    get_call_center_cases,
    DomainLite,
    get_call_center_domains)
from corehq.apps.domain.models import Domain
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.domain.signals import commcare_domain_post_save
from corehq.apps.users.util import format_username
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.bulkupload import create_or_update_users_and_groups
from django.test import TestCase, SimpleTestCase, override_settings

from corehq.elastic import get_es_new, send_to_elasticsearch
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors, FormAccessors
from corehq.pillows.mappings.domain_mapping import DOMAIN_INDEX_INFO
from corehq.util.context_managers import drop_connected_signals
from corehq.util.elastic import ensure_index_deleted
from dimagi.utils.couch.undo import DELETED_SUFFIX
from pillowtop.es_utils import initialize_index

TEST_DOMAIN = 'cc-util-test'
CASE_TYPE = 'cc-flw'


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=False)
class CallCenterUtilsTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super(CallCenterUtilsTests, cls).setUpClass()
        cls.domain = create_domain(TEST_DOMAIN)
        cls.user = CommCareUser.create(TEST_DOMAIN, 'user1', '***')
        cls.user_id = cls.user.user_id

        cls.domain.call_center_config.enabled = True
        cls.domain.call_center_config.case_owner_id = cls.user.user_id
        cls.domain.call_center_config.case_type = CASE_TYPE
        cls.domain.save()

    @classmethod
    def tearDownClass(cls):
        cls.user.delete()
        cls.domain.delete()
        super(CallCenterUtilsTests, cls).tearDownClass()

    def tearDown(self):
        delete_all_cases()

    def test_sync(self):
        sync_call_center_user_case(self.user)
        case = self._get_user_case()
        self.assertIsNotNone(case)
        self.assertEqual(case.name, self.user.username)
        self.assertEqual(case.get_case_property('username'), self.user.raw_username)
        self.assertIsNotNone(case.get_case_property('language'))
        self.assertIsNotNone(case.get_case_property('phone_number'))

    def test_sync_full_name(self):
        other_user = CommCareUser.create(TEST_DOMAIN, 'user7', '***')
        self.addCleanup(other_user.delete)
        name = 'Ricky Bowwood'
        other_user.set_full_name(name)
        sync_call_center_user_case(other_user)
        case = self._get_user_case(other_user._id)
        self.assertIsNotNone(case)
        self.assertEqual(case.name, name)

    def test_sync_inactive(self):
        sync_call_center_user_case(self.user)
        case = self._get_user_case()
        self.assertIsNotNone(case)

        self.user.is_active = False
        sync_call_center_user_case(self.user)
        case = self._get_user_case()
        self.assertTrue(case.closed)

    def test_sync_retired(self):
        sync_call_center_user_case(self.user)
        case = self._get_user_case()
        self.assertIsNotNone(case)

        self.user.base_doc += DELETED_SUFFIX
        sync_call_center_user_case(self.user)
        case = self._get_user_case()
        self.assertTrue(case.closed)

    def test_sync_update_update(self):
        other_user = CommCareUser.create(TEST_DOMAIN, 'user2', '***')
        self.addCleanup(other_user.delete)
        sync_call_center_user_case(other_user)
        case = self._get_user_case(other_user._id)
        self.assertIsNotNone(case)
        self.assertEqual(case.name, other_user.username)

        name = 'Ricky Bowwood'
        other_user.set_full_name(name)
        sync_call_center_user_case(other_user)
        case = self._get_user_case(other_user._id)
        self.assertEqual(case.name, name)

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
        case = self._get_user_case()
        self.assertIsNotNone(case)
        self.assertEqual(case.get_case_property('blank_val'), '')
        self.assertEqual(case.get_case_property('ok'), 'good')

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
        case = self._get_user_case()
        self.assertEqual(case.owner_id, cases[0].owner_id)

    def test_opened_by_id_is_system(self):
        sync_call_center_user_case(self.user)
        case = self._get_user_case()
        self.assertEqual(case.opened_by, CALLCENTER_USER)

    def _get_user_case(self, user_id=None):
        return CaseAccessors(TEST_DOMAIN).get_case_by_domain_hq_user_id(user_id or self.user._id, CASE_TYPE)


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class CallCenterUtilsTestsSQL(CallCenterUtilsTests):
    pass


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=False)
class CallCenterUtilsUserCaseTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super(CallCenterUtilsUserCaseTests, cls).setUpClass()
        cls.domain = create_domain(TEST_DOMAIN)
        cls.domain.usercase_enabled = True
        cls.domain.save()

    def setUp(self):
        self.user = CommCareUser.create(TEST_DOMAIN, 'user1', '***', commit=False)  # Don't commit yet

    def tearDown(self):
        self.user.delete()

    @classmethod
    def tearDownClass(cls):
        delete_all_cases()
        cls.domain.delete()
        super(CallCenterUtilsUserCaseTests, cls).tearDownClass()

    def test_sync_usercase_custom_user_data_on_create(self):
        """
        Custom user data should be synced when the user is created
        """
        self.user.user_data = {
            'completed_training': 'yes',
        }
        self.user.save()
        case = CaseAccessors(TEST_DOMAIN).get_case_by_domain_hq_user_id(self.user._id, USERCASE_TYPE)
        self.assertIsNotNone(case)
        self.assertEqual(case.dynamic_case_properties()['completed_training'], 'yes')

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
        case = CaseAccessors(TEST_DOMAIN).get_case_by_domain_hq_user_id(self.user._id, USERCASE_TYPE)
        self.assertEqual(case.dynamic_case_properties()['completed_training'], 'yes')
        self._check_update_matches(case, {'completed_training': 'yes'})

    def test_sync_usercase_overwrite_hq_props(self):
        """
        Test that setting custom user data for owner_id and case_type don't change the case
        """
        self.user.user_data = {
            'owner_id': 'someone else',
            'case_type': 'bob',
        }
        self.user.save()
        case = CaseAccessors(TEST_DOMAIN).get_case_by_domain_hq_user_id(self.user._id, USERCASE_TYPE)
        self.assertEqual(case.owner_id, self.user.get_id)
        self.assertEqual(case.type, USERCASE_TYPE)
        self.assertEqual(1, len(case.xform_ids))

    def _check_update_matches(self, case, expected_update):
        last_form = FormAccessors(TEST_DOMAIN).get_form(case.xform_ids[-1])
        case_update = get_case_updates(last_form)[0]
        self.assertDictEqual(case_update.update_block, expected_update)

    def test_reactivate_user(self):
        """Confirm that reactivating a user re-opens its user case."""
        self.user.save()
        user_case = CaseAccessors(TEST_DOMAIN).get_case_by_domain_hq_user_id(self.user._id, USERCASE_TYPE)
        self.assertIsNotNone(user_case)

        self.user.is_active = False
        self.user.save()
        user_case = CaseAccessors(TEST_DOMAIN).get_case_by_domain_hq_user_id(self.user._id, USERCASE_TYPE)
        self.assertTrue(user_case.closed)

        self.user.is_active = True
        self.user.save()
        user_case = CaseAccessors(TEST_DOMAIN).get_case_by_domain_hq_user_id(self.user._id, USERCASE_TYPE)
        self.assertFalse(user_case.closed)

    def test_update_deactivated_user(self):
        """
        Confirm that updating a deactivated user also updates the user case.
        """
        self.user.save()
        user_case = CaseAccessors(TEST_DOMAIN).get_case_by_domain_hq_user_id(self.user._id, USERCASE_TYPE)
        self.assertIsNotNone(user_case)

        self.user.is_active = False
        self.user.save()
        user_case = CaseAccessors(TEST_DOMAIN).get_case_by_domain_hq_user_id(self.user._id, USERCASE_TYPE)
        self.assertTrue(user_case.closed)

        self.user.user_data = {'foo': 'bar'}
        self.user.save()
        user_case = CaseAccessors(TEST_DOMAIN).get_case_by_domain_hq_user_id(self.user._id, USERCASE_TYPE)
        self.assertTrue(user_case.closed)
        self.assertEqual(user_case.dynamic_case_properties()['foo'], 'bar')

    def test_update_and_reactivate_in_one_save(self):
        """
        Confirm that a usercase can be updated and reactived in a single save of the user model
        """
        """
        Confirm that updating a deactivated user also updates the user case.
        """
        self.user.save()
        user_case = CaseAccessors(TEST_DOMAIN).get_case_by_domain_hq_user_id(self.user._id, USERCASE_TYPE)
        self.assertIsNotNone(user_case)

        self.user.is_active = False
        self.user.save()
        user_case = CaseAccessors(TEST_DOMAIN).get_case_by_domain_hq_user_id(self.user._id, USERCASE_TYPE)
        self.assertTrue(user_case.closed)

        self.user.user_data = {'foo': 'bar'}
        self.user.is_active = True
        self.user.save()
        user_case = CaseAccessors(TEST_DOMAIN).get_case_by_domain_hq_user_id(self.user._id, USERCASE_TYPE)
        self.assertFalse(user_case.closed)
        self.assertEqual(user_case.dynamic_case_properties()['foo'], 'bar')

    def test_update_no_change(self):
        self.user.user_data = {
            'numeric': 123,
        }
        self.user.save()
        user_case = CaseAccessors(TEST_DOMAIN).get_case_by_domain_hq_user_id(self.user._id, USERCASE_TYPE)
        self.assertIsNotNone(user_case)
        self.assertEqual(1, len(user_case.xform_ids))

        self.user.save()
        user_case = CaseAccessors(TEST_DOMAIN).get_case_by_domain_hq_user_id(self.user._id, USERCASE_TYPE)
        self.assertEqual(1, len(user_case.xform_ids))

    def test_bulk_upload_usercases(self):
        self.user.username = format_username('bushy_top', TEST_DOMAIN)
        self.user.save()
        user_upload = [{
            'username': self.user.raw_username,
            'user_id': self.user.user_id,
            'name': 'James McNulty',
            'language': None,
            'is_active': 'True',
            'phone-number': self.user.phone_number,
            'password': 123,
            'email': None
        }, {
            'username': 'the_bunk',
            'user_id': '',
            'name': 'William Moreland',
            'language': None,
            'is_active': 'True',
            'phone-number': '23424123',
            'password': 123,
            'email': None
        }]
        results = create_or_update_users_and_groups(
            TEST_DOMAIN,
            list(user_upload),
            list([]),
        )
        self.assertEqual(results['errors'], [])

        accessor = CaseAccessors(TEST_DOMAIN)
        old_user_case = accessor.get_case_by_domain_hq_user_id(self.user._id, USERCASE_TYPE)
        self.assertEqual(old_user_case.owner_id, self.user.get_id)
        self.assertEqual(2, len(old_user_case.xform_ids))

        new_user = CommCareUser.get_by_username(format_username('the_bunk', TEST_DOMAIN))
        self.addCleanup(new_user.delete)
        new_user_case = accessor.get_case_by_domain_hq_user_id(new_user._id, USERCASE_TYPE)
        self.assertEqual(new_user_case.owner_id, new_user.get_id)
        self.assertEqual(1, len(new_user_case.xform_ids))


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class CallCenterUtilsUserCaseTestsSQL(CallCenterUtilsUserCaseTests):
    pass


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


class CallCenterDomainTest(SimpleTestCase):
    def setUp(self):
        self.index_info = DOMAIN_INDEX_INFO
        self.elasticsearch = get_es_new()
        ensure_index_deleted(self.index_info.index)
        initialize_index(self.elasticsearch, self.index_info)
        import time
        time.sleep(1)  # without this we get a 503 response about 30% of the time

    def tearDown(self):
        ensure_index_deleted(self.index_info.index)

    def test_get_call_center_domains(self):
        _create_domain('cc-dom1', True, True, 'flw', 'user1', False)
        _create_domain('cc-dom2', True, False, 'aww', None, True)
        _create_domain('cc-dom3', False, False, '', 'user2', False)  # case type missing
        _create_domain('cc-dom3', False, False, 'flw', None, False)  # owner missing
        self.elasticsearch.indices.refresh(self.index_info.index)

        domains = get_call_center_domains()
        self.assertEqual(2, len(domains))
        [dom1] = [dom for dom in domains if dom.name == 'cc-dom1']
        [dom2] = [dom for dom in domains if dom.name == 'cc-dom2']
        self.assertEqual('flw', dom1.cc_case_type)
        self.assertTrue(dom1.use_fixtures)
        self.assertEqual('aww', dom2.cc_case_type)
        self.assertFalse(dom2.use_fixtures)


def _create_domain(name, cc_enabled, cc_use_fixtures, cc_case_type, cc_case_owner_id, use_location_as_owner):
    with drop_connected_signals(commcare_domain_post_save):
        domain = Domain(
            _id=uuid.uuid4().hex,
            name=name,
            is_active=True,
            date_created=datetime.utcnow(),
        )
        domain.call_center_config.enabled = cc_enabled
        domain.call_center_config.use_fixtures = cc_use_fixtures
        domain.call_center_config.case_type = cc_case_type
        domain.call_center_config.case_owner_id = cc_case_owner_id
        domain.call_center_config.use_user_location_as_owner = use_location_as_owner

        send_to_elasticsearch(
            'domains',
            doc=domain.to_json(),
        )


class CallCenterDomainMockTest(TestCase):

    _call_center_domain_mock = mock.patch(
        'corehq.apps.callcenter.data_source.call_center_data_source_configuration_provider'
    )

    @classmethod
    def setUpClass(cls):
        super(CallCenterDomainMockTest, cls).setUpClass()
        cls._call_center_domain_mock.start()

    @classmethod
    def tearDownClass(cls):
        super(CallCenterDomainMockTest, cls).tearDownClass()
        cls._call_center_domain_mock.stop()
