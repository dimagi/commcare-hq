from collections import namedtuple
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.xml import V2
from corehq.apps.callcenter.const import DATE_RANGES, WEEK1, WEEK0, MONTH0, MONTH1
from corehq.apps.callcenter.indicator_sets import AAROHI_MOTHER_FORM, CallCenterIndicators, \
    cache_key, CachedIndicators
from corehq.apps.callcenter.models import CallCenterIndicatorConfig, TypedIndicator
from corehq.apps.callcenter.utils import sync_call_center_user_case
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.callcenter.tests.sql_fixture import load_data, load_custom_data, clear_data
from corehq.apps.groups.models import Group
from corehq.apps.hqcase.utils import submit_case_blocks, get_case_by_domain_hq_user_id
from corehq.apps.users.models import CommCareUser
from django.test import TestCase

from django.core import cache

CASE_TYPE = 'cc_flw'

locmem_cache = cache.caches['locmem']


def create_domain_and_user(domain_name, username):
    domain = create_domain(domain_name)
    user = CommCareUser.create(domain_name, username, '***')

    domain.call_center_config.enabled = True
    domain.call_center_config.case_owner_id = user.user_id
    domain.call_center_config.case_type = CASE_TYPE
    domain.save()

    sync_call_center_user_case(user)
    return domain, user


def create_cases_for_types(domain, case_types):
    for i, case_type in enumerate(case_types):
        submit_case_blocks(
            CaseBlock(
                create=True,
                case_id='person%s' % i,
                case_type=case_type,
                user_id='user%s' % i,
                version=V2,
            ).as_string(), domain)


def get_indicators(prefix, values, case_type=None, is_legacy=False, limit_ranges=None):
    """
    Generate indicators e.g. cases_opened_week0, cases_opened_{case_type}_week0 etc.
    """
    ranges = DATE_RANGES
    limit_ranges = limit_ranges or DATE_RANGES
    data = {}
    separator = '' if is_legacy else '_'
    infix = '{}{}{}'.format(separator, case_type, separator) if case_type else separator
    for i, r in enumerate(ranges):
        if r in limit_ranges:
            r = r.title() if is_legacy else r
            indicator_name = '{prefix}{infix}{suffix}'.format(
                prefix=prefix,
                infix=infix,
                suffix=r)
            data[indicator_name] = values[i]

    return data


StaticIndicators = namedtuple('StaticIndicators', 'name, values, is_legacy, infix')


def expected_standard_indicators(no_data=False, include_legacy=True, include_totals=True, case_types=None, limit_ranges=None):
    case_types = case_types if case_types is not None else ['person', 'dog']
    expected = {}
    expected_values = []
    if include_totals:
        expected_values.extend([
            StaticIndicators('forms_submitted', [2L, 4L, 7L, 0L], False, None),
            StaticIndicators('cases_total', [4L, 4L, 6L, 5L], False, None),
            StaticIndicators('cases_opened', [0L, 1L, 3L, 5L], False, None),
            StaticIndicators('cases_closed', [0L, 0L, 2L, 2L], False, None),
            StaticIndicators('cases_active', [0L, 1L, 3L, 5L], False, None),
        ])

    if 'dog' in case_types:
        expected_values.extend ([
            StaticIndicators('cases_total', [3L, 3L, 3L, 5L], False, 'dog'),
            StaticIndicators('cases_opened', [0L, 0L, 0L, 5L], False, 'dog'),
            StaticIndicators('cases_closed', [0L, 0L, 0L, 2L], False, 'dog'),
            StaticIndicators('cases_active', [0L, 0L, 0L, 5L], False, 'dog')
        ])

    if 'person' in case_types:
        expected_values.extend ([
            StaticIndicators('cases_total', [1L, 1L, 3L, 0L], False, 'person'),
            StaticIndicators('cases_opened', [0L, 1L, 3L, 0L], False, 'person'),
            StaticIndicators('cases_closed', [0L, 0L, 2L, 0L], False, 'person'),
            StaticIndicators('cases_active', [0L, 1L, 3L, 0L], False, 'person'),
        ])

    if include_legacy:
        expected_values.extend([
            StaticIndicators('formsSubmitted', [2L, 4L, 7L, 0L], True, None),
            StaticIndicators('casesUpdated', [0L, 1L, 3L, 5L], True, None),
        ])

        expected['totalCases'] = 0L if no_data else 5L

    for val in expected_values:
        values = [0L] * 4 if no_data else val.values
        expected.update(get_indicators(val.name, values, val.infix, val.is_legacy, limit_ranges))

    return expected


class BaseCCTests(TestCase):
    def setUp(self):
        locmem_cache.clear()

    def _test_indicators(self, user, data_set, expected):
        user_case = get_case_by_domain_hq_user_id(user.domain, user.user_id, CASE_TYPE)
        case_id = user_case.case_id
        self.assertIn(case_id, data_set)

        user_data = data_set[case_id]

        mismatches = []
        for k, v in expected.items():
            expected_value = user_data.pop(k, None)
            if expected_value != v:
                mismatches.append('{}: {} != {}'.format(k, v, expected_value))

        if mismatches:
            self.fail('Mismatching indicators:\n{}'.format('\t\n'.join(mismatches)))

        if user_data:
            self.fail('Additional indicators:\n{}'.format('\t\n'.join(user_data.keys())))


class CallCenterTests(BaseCCTests):
    @classmethod
    def setUpClass(cls):
        cls.cc_domain, cls.cc_user = create_domain_and_user('callcentertest', 'user1')
        load_data(cls.cc_domain.name, cls.cc_user.user_id)
        cls.cc_user_no_data = CommCareUser.create(cls.cc_domain.name, 'user3', '***')

        cls.aarohi_domain, cls.aarohi_user = create_domain_and_user('aarohi', 'user2')
        load_custom_data(cls.aarohi_domain.name, cls.aarohi_user.user_id, xmlns=AAROHI_MOTHER_FORM)

        # create one case of each type so that we get the indicators where there is no data for the period
        create_cases_for_types(cls.cc_domain.name, ['person', 'dog'])

    @classmethod
    def tearDownClass(cls):
        cls.cc_domain.delete()
        cls.aarohi_domain.delete()
        clear_data()

    def check_cc_indicators(self, data_set, expected):
        self._test_indicators(self.cc_user, data_set, expected)
        expected_no_data = expected_standard_indicators(no_data=True)
        self._test_indicators(self.cc_user_no_data, data_set, expected_no_data)

    def test_standard_indicators(self):
        indicator_set = CallCenterIndicators(
            self.cc_domain.name,
            self.cc_domain.default_timezone,
            self.cc_domain.call_center_config.case_type,
            self.cc_user,
            custom_cache=locmem_cache
        )
        self.assertEqual(
            set(indicator_set.user_to_case_map.keys()),
            set([self.cc_user.get_id, self.cc_user_no_data.get_id])
        )
        self.assertEqual(indicator_set.users_needing_data, set([self.cc_user.get_id, self.cc_user_no_data.get_id]))
        self.assertEqual(indicator_set.owners_needing_data, set([self.cc_user.get_id, self.cc_user_no_data.get_id]))
        self.check_cc_indicators(indicator_set.get_data(), expected_standard_indicators())

    def test_standard_indicators_no_legacy(self):
        config = CallCenterIndicatorConfig.default_config(self.cc_domain.name, include_legacy=False)

        indicator_set = CallCenterIndicators(
            self.cc_domain.name,
            self.cc_domain.default_timezone,
            self.cc_domain.call_center_config.case_type,
            self.cc_user,
            custom_cache=locmem_cache,
            indicator_config=config
        )
        self._test_indicators(
            self.cc_user,
            indicator_set.get_data(),
            expected_standard_indicators(include_legacy=False))

    def test_standard_indicators_case_totals_only(self):
        config = CallCenterIndicatorConfig.default_config(self.cc_domain.name, include_legacy=False)
        config.cases_total.all_types = False
        config.cases_opened.all_types = False
        config.cases_closed.all_types = False
        config.cases_active.all_types = False

        indicator_set = CallCenterIndicators(
            self.cc_domain.name,
            self.cc_domain.default_timezone,
            self.cc_domain.call_center_config.case_type,
            self.cc_user,
            custom_cache=locmem_cache,
            indicator_config=config
        )
        self._test_indicators(
            self.cc_user,
            indicator_set.get_data(),
            expected_standard_indicators(
                include_legacy=False,
                include_totals=True,
                case_types=[])
        )

    def test_standard_indicators_load_config_from_db(self):
        config = CallCenterIndicatorConfig.default_config(self.cc_domain.name, include_legacy=False)
        config.save()

        self.addCleanup(config.delete)

        indicator_set = CallCenterIndicators(
            self.cc_domain.name,
            self.cc_domain.default_timezone,
            self.cc_domain.call_center_config.case_type,
            self.cc_user,
            custom_cache=locmem_cache,
        )
        self._test_indicators(
            self.cc_user,
            indicator_set.get_data(),
            expected_standard_indicators(include_legacy=False))
        
    def test_standard_indicators_case_dog_only(self):
        config = CallCenterIndicatorConfig.default_config(self.cc_domain.name, include_legacy=False)
        config.forms_submitted.active = False

        def dog_only(conf):
            conf.total.active = False
            conf.all_types = False
            conf.types = [TypedIndicator(active=True, date_ranges=[WEEK0, MONTH0], type='dog')]

        dog_only(config.cases_total)
        dog_only(config.cases_opened)
        dog_only(config.cases_closed)
        dog_only(config.cases_active)

        indicator_set = CallCenterIndicators(
            self.cc_domain.name,
            self.cc_domain.default_timezone,
            self.cc_domain.call_center_config.case_type,
            self.cc_user,
            custom_cache=locmem_cache,
            indicator_config=config
        )
        self._test_indicators(
            self.cc_user,
            indicator_set.get_data(),
            expected_standard_indicators(
                include_legacy=False,
                include_totals=False,
                case_types=['dog'],
                limit_ranges=[WEEK0, MONTH0])
        )

    def test_standard_indicators_case_week1_only(self):
        config = CallCenterIndicatorConfig.default_config(self.cc_domain.name, include_legacy=False)
        config.forms_submitted.date_ranges = [WEEK1]
        config.cases_total.total.date_ranges = [WEEK1]
        config.cases_opened.total.date_ranges = [WEEK1]
        config.cases_closed.total.date_ranges = [WEEK1]
        config.cases_active.total.date_ranges = [WEEK1]

        indicator_set = CallCenterIndicators(
            self.cc_domain.name,
            self.cc_domain.default_timezone,
            self.cc_domain.call_center_config.case_type,
            self.cc_user,
            custom_cache=locmem_cache,
            indicator_config=config
        )
        self._test_indicators(
            self.cc_user,
            indicator_set.get_data(),
            expected_standard_indicators(
                include_legacy=False,
                include_totals=True,
                limit_ranges=[WEEK1])
        )

    def test_sync_log(self):
        user_case = get_case_by_domain_hq_user_id(self.cc_domain.name, self.cc_user.get_id, CASE_TYPE)

        indicator_set = CallCenterIndicators(
            self.cc_domain.name,
            self.cc_domain.default_timezone,
            self.cc_domain.call_center_config.case_type,
            self.cc_user,
            custom_cache=locmem_cache,
            override_cases=[user_case]
        )
        self.assertEqual(indicator_set.user_to_case_map.keys(), [self.cc_user.get_id])
        self.assertEqual(indicator_set.users_needing_data, set([self.cc_user.get_id]))
        self.assertEqual(indicator_set.owners_needing_data, set([self.cc_user.get_id]))
        self._test_indicators(self.cc_user, indicator_set.get_data(), expected_standard_indicators())

    def test_custom_indicators(self):
        expected = {'totalCases': 0L}
        expected.update(get_indicators('formsSubmitted', [3L, 3L, 9L, 0L], is_legacy=True))
        expected.update(get_indicators('forms_submitted', [3L, 3L, 9L, 0L]))
        expected.update(get_indicators('casesUpdated', [0L, 0L, 0L, 0L], is_legacy=True))
        expected.update(get_indicators('cases_total', [0L, 0L, 0L, 0L]))
        expected.update(get_indicators('cases_opened', [0L, 0L, 0L, 0L]))
        expected.update(get_indicators('cases_closed', [0L, 0L, 0L, 0L]))
        expected.update(get_indicators('cases_active', [0L, 0L, 0L, 0L]))

        # custom
        expected.update(get_indicators('motherForms', [3L, 3L, 9L, 0L], is_legacy=True))
        expected.update(get_indicators('childForms', [0L, 0L, 0L, 0L], is_legacy=True))
        expected.update(get_indicators('motherDuration', [3L, 4L, 4L, 0L], is_legacy=True))

        indicator_set = CallCenterIndicators(
            self.aarohi_domain.name,
            self.aarohi_domain.default_timezone,
            self.aarohi_domain.call_center_config.case_type,
            self.aarohi_user,
            custom_cache=locmem_cache
        )
        self._test_indicators(
            self.aarohi_user,
            indicator_set.get_data(),
            expected
        )

    def test_caching(self):
        user_case = get_case_by_domain_hq_user_id(self.cc_domain.name, self.cc_user._id, CASE_TYPE)
        expected_indicators = {'a': 1, 'b': 2}
        cached_data = CachedIndicators(
            user_id=self.cc_user.get_id,
            case_id=user_case.case_id,
            domain=self.cc_domain.name,
            indicators=expected_indicators
        )

        indicator_set = CallCenterIndicators(
            self.cc_domain.name,
            self.cc_domain.default_timezone,
            self.cc_domain.call_center_config.case_type,
            self.cc_user,
            custom_cache=locmem_cache
        )
        locmem_cache.set(cache_key(self.cc_user.get_id, indicator_set.reference_date), cached_data.to_json())

        self.assertEqual(
            set(indicator_set.user_to_case_map.keys()),
            set([self.cc_user.get_id, self.cc_user_no_data.get_id])
        )
        self.assertEquals(indicator_set.users_needing_data, set([self.cc_user_no_data.get_id]))
        self.assertEqual(indicator_set.owners_needing_data, set([self.cc_user_no_data.get_id]))
        self.check_cc_indicators(indicator_set.get_data(), expected_indicators)

    def test_no_cases_owned_by_user(self):
        """
        Test to verify that only data belonging to users managed by the supervisor is returned.
        """
        indicator_set = CallCenterIndicators(
            self.cc_domain.name,
            self.cc_domain.default_timezone,
            self.cc_domain.call_center_config.case_type,
            self.cc_user_no_data,
            custom_cache=locmem_cache
        )
        self.assertEqual(indicator_set.user_to_case_map.keys(), [])
        self.assertEqual(indicator_set.users_needing_data, set())
        self.assertEqual(indicator_set.owners_needing_data, set())
        self.assertEqual(indicator_set.get_data(), {})


class CallCenterSupervisorGroupTest(BaseCCTests):
    @classmethod
    def setUpClass(cls):
        domain_name = 'cc_test_supervisor_group'
        cls.domain = create_domain(domain_name)
        cls.supervisor = CommCareUser.create(domain_name, 'supervisor@' + domain_name, '***')

        cls.supervisor_group = Group(
            domain=domain_name,
            name='supervisor group',
            case_sharing=True,
            users=[cls.supervisor.get_id]
        )
        cls.supervisor_group.save()

        cls.domain.call_center_config.enabled = True
        cls.domain.call_center_config.case_owner_id = cls.supervisor_group.get_id
        cls.domain.call_center_config.case_type = 'cc_flw'
        cls.domain.save()

        cls.user = CommCareUser.create(domain_name, 'user@' + domain_name, '***')
        sync_call_center_user_case(cls.user)

        load_data(domain_name, cls.user.user_id)

        # create one case of each type so that we get the indicators where there is no data for the period
        create_cases_for_types(domain_name, ['person', 'dog'])

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()
        clear_data()

    def test_users_assigned_via_group(self):
        """
        Ensure that users who are assigned to the supervisor via a group are also included
        in final data set.
        """
        indicator_set = CallCenterIndicators(
            self.domain.name,
            self.domain.default_timezone,
            self.domain.call_center_config.case_type,
            self.supervisor,
            custom_cache=locmem_cache
        )
        self.assertEqual(indicator_set.user_to_case_map.keys(), [self.user.get_id])
        self.assertEqual(indicator_set.users_needing_data, set([self.user.get_id]))
        self.assertEqual(indicator_set.owners_needing_data, set([self.user.get_id]))
        self._test_indicators(self.user, indicator_set.get_data(), expected_standard_indicators())


class CallCenterCaseSharingTest(BaseCCTests):
    @classmethod
    def setUpClass(cls):
        domain_name = 'cc_test_case_sharing'
        cls.domain = create_domain(domain_name)
        cls.supervisor = CommCareUser.create(domain_name, 'supervisor@' + domain_name, '***')

        cls.domain.call_center_config.enabled = True
        cls.domain.call_center_config.case_owner_id = cls.supervisor.get_id
        cls.domain.call_center_config.case_type = 'cc_flw'
        cls.domain.save()

        cls.user = CommCareUser.create(domain_name, 'user@' + domain_name, '***')
        sync_call_center_user_case(cls.user)

        cls.group = Group(
            domain=domain_name,
            name='case sharing group',
            case_sharing=True,
            users=[cls.user.user_id]
        )
        cls.group.save()

        load_data(
            domain_name,
            cls.user.user_id,
            'not this user',
            cls.group.get_id,
            case_opened_by=cls.user.user_id,
            case_closed_by=cls.user.user_id)

        # create one case of each type so that we get the indicators where there is no data for the period
        create_cases_for_types(domain_name, ['person', 'dog'])

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()
        clear_data()

    def test_cases_owned_by_group(self):
        """
        Ensure that indicators include cases owned by a case sharing group the user is part of.
        """
        indicator_set = CallCenterIndicators(
            self.domain.name,
            self.domain.default_timezone,
            self.domain.call_center_config.case_type,
            self.supervisor,
            custom_cache=locmem_cache
        )
        self.assertEqual(indicator_set.user_to_case_map.keys(), [self.user.get_id])
        self.assertEqual(indicator_set.users_needing_data, set([self.user.get_id]))
        self.assertEqual(indicator_set.owners_needing_data, set([self.user.get_id, self.group.get_id]))
        expected = expected_standard_indicators()
        expected['totalCases'] = 0L  # no cases with user_id = self.user.get_id
        self._test_indicators(self.user, indicator_set.get_data(), expected)


class CallCenterTestOpenedClosed(BaseCCTests):
    @classmethod
    def setUpClass(cls):
        domain_name = 'cc_test_opened_closed'
        cls.domain = create_domain(domain_name)
        cls.supervisor = CommCareUser.create(domain_name, 'supervisor@' + domain_name, '***')

        cls.domain.call_center_config.enabled = True
        cls.domain.call_center_config.case_owner_id = cls.supervisor.get_id
        cls.domain.call_center_config.case_type = 'cc_flw'
        cls.domain.save()

        cls.user = CommCareUser.create(domain_name, 'user@' + domain_name, '***')
        sync_call_center_user_case(cls.user)

        load_data(domain_name, cls.user.user_id, case_opened_by='not me', case_closed_by='not me')

        # create one case of each type so that we get the indicators where there is no data for the period
        create_cases_for_types(domain_name, ['person', 'dog'])

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()
        clear_data()

    def test_opened_closed(self):
        """
        Test that cases_closed and cases_opened indicators count based on the user that
        opened / closed the case and not the case owner.
        """
        indicator_set = CallCenterIndicators(
            self.domain.name,
            self.domain.default_timezone,
            self.domain.call_center_config.case_type,
            self.supervisor,
            custom_cache=locmem_cache
        )
        expected = expected_standard_indicators()

        # cases opened / closed by another user so expect 0
        for key in expected:
            if key.startswith('cases_opened') or key.startswith('cases_closed'):
                expected[key] = 0L
        self._test_indicators(self.user, indicator_set.get_data(), expected)
