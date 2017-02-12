import uuid
from collections import namedtuple

from django.conf import settings
from django.test.utils import override_settings

from casexml.apps.case.mock import CaseBlock
from corehq.apps.callcenter.const import DATE_RANGES, WEEK1, WEEK0, MONTH0, MONTH1
from corehq.apps.callcenter.indicator_sets import AAROHI_MOTHER_FORM, CallCenterIndicators, \
    cache_key, CachedIndicators
from corehq.apps.callcenter.models import CallCenterIndicatorConfig, TypedIndicator
from corehq.apps.callcenter.utils import sync_call_center_user_case, CallCenterCase
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.callcenter.tests.sql_fixture import load_data, load_custom_data, clear_data
from corehq.apps.groups.models import Group
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.users.models import CommCareUser
from django.test import TestCase

from django.core import cache

from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.tests.utils import conditionally_run_with_all_backends
from corehq.sql_db.connections import connection_manager
from corehq.sql_db.tests.utils import temporary_database

CASE_TYPE = 'cc_flw'

locmem_cache = cache.caches['locmem']


def create_domain_and_user(domain_name, username):
    domain = create_domain(domain_name)
    user = CommCareUser.get_by_username(username)
    if user:
        user.delete()
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
                case_id=uuid.uuid4().hex,
                case_type=case_type,
                user_id=uuid.uuid4().hex,
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
    domain_name = None

    def setUp(self):
        super(BaseCCTests, self).setUp()
        locmem_cache.clear()
        CaseAccessors.get_case_types.clear(CaseAccessors(self.domain_name))

    def tearDown(self):
        CaseAccessors.get_case_types.clear(CaseAccessors(self.domain_name))
        super(BaseCCTests, self).tearDown()

    def _test_indicators(self, user, data_set, expected):
        user_case = CaseAccessors(user.domain).get_case_by_domain_hq_user_id(user.user_id, CASE_TYPE)
        case_id = user_case.case_id
        self.assertIn(case_id, data_set)

        user_data = data_set[case_id]

        mismatches = []
        for indicator_key, expected_value in expected.items():
            actual_value = user_data.pop(indicator_key, None)
            if actual_value != expected_value:
                mismatches.append('{}: {} != {}'.format(indicator_key, expected_value, actual_value))

        if mismatches:
            self.fail('Mismatching indicators:\n{}'.format('\t\n'.join(sorted(mismatches))))

        if user_data:
            self.fail('Additional indicators:\n{}'.format('\t\n'.join(user_data.keys())))


class CallCenterTests(BaseCCTests):
    domain_name = 'callcentertest'

    @classmethod
    def setUpClass(cls):
        super(CallCenterTests, cls).setUpClass()
        cls.cc_domain, cls.cc_user = create_domain_and_user(cls.domain_name, 'user1')
        load_data(cls.cc_domain.name, cls.cc_user.user_id)
        cls.cc_user_no_data = CommCareUser.create(cls.cc_domain.name, 'user3', '***')

        cls.aarohi_domain, cls.aarohi_user = create_domain_and_user('aarohi', 'user2')
        load_custom_data(cls.aarohi_domain.name, cls.aarohi_user.user_id, xmlns=AAROHI_MOTHER_FORM)

        # create one case of each type so that we get the indicators where there is no data for the period
        create_cases_for_types(cls.cc_domain.name, ['person', 'dog'])

    @classmethod
    def tearDownClass(cls):
        CaseAccessors.get_case_types.clear(CaseAccessors(cls.aarohi_domain.name))
        clear_data(cls.aarohi_domain.name)
        clear_data(cls.cc_domain.name)
        cls.cc_user.delete()
        cls.cc_user_no_data.delete()
        cls.cc_domain.delete()
        cls.aarohi_user.delete()
        cls.aarohi_domain.delete()
        super(CallCenterTests, cls).tearDownClass()

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
        config = CallCenterIndicatorConfig.default_config(include_legacy=False)

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
        config = CallCenterIndicatorConfig.default_config(include_legacy=False)
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

    def test_standard_indicators_case_dog_only(self):
        config = CallCenterIndicatorConfig.default_config(include_legacy=False)
        config.forms_submitted.enabled = False

        def dog_only(conf):
            conf.totals.enabled = False
            conf.all_types = False
            conf.by_type = [TypedIndicator(enabled=True, date_ranges={WEEK0, MONTH0}, type='dog')]

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
        config = CallCenterIndicatorConfig.default_config(include_legacy=False)
        config.forms_submitted.date_ranges = {WEEK1}
        config.cases_total.totals.date_ranges = {WEEK1}
        config.cases_opened.totals.date_ranges = {WEEK1}
        config.cases_closed.totals.date_ranges = {WEEK1}
        config.cases_active.totals.date_ranges = {WEEK1}

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
        user_case = CaseAccessors(self.cc_domain.name).get_case_by_domain_hq_user_id(self.cc_user.get_id, CASE_TYPE)

        indicator_set = CallCenterIndicators(
            self.cc_domain.name,
            self.cc_domain.default_timezone,
            self.cc_domain.call_center_config.case_type,
            self.cc_user,
            custom_cache=locmem_cache,
            override_cases=[CallCenterCase.from_case(user_case)]
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
            custom_cache=locmem_cache,
        )
        self._test_indicators(
            self.aarohi_user,
            indicator_set.get_data(),
            expected
        )

    def test_custom_indicators_limited(self):
        expected = {}

        # custom
        expected.update(
            get_indicators('motherForms', [3L, None, 9L, None], is_legacy=True, limit_ranges=[WEEK0, MONTH0])
        )
        expected.update(
            get_indicators('childForms', [None, 0L, None, None], is_legacy=True, limit_ranges=[WEEK1])
        )
        expected.update(
            get_indicators('motherDuration', [None, None, None, 0L], is_legacy=True, limit_ranges=[MONTH1])
        )

        indicator_config = CallCenterIndicatorConfig()
        indicator_config.custom_form = [
            TypedIndicator(type='motherForms', date_range=WEEK0),
            TypedIndicator(type='motherForms', date_range=MONTH0),
            TypedIndicator(type='childForms', date_range=WEEK1),
            TypedIndicator(type='motherDuration', date_range=MONTH1),
        ]
        indicator_set = CallCenterIndicators(
            self.aarohi_domain.name,
            self.aarohi_domain.default_timezone,
            self.aarohi_domain.call_center_config.case_type,
            self.aarohi_user,
            custom_cache=locmem_cache,
            indicator_config=indicator_config
        )
        self._test_indicators(
            self.aarohi_user,
            indicator_set.get_data(),
            expected
        )

    def test_caching(self):
        user_case = CaseAccessors(self.cc_domain.name).get_case_by_domain_hq_user_id(self.cc_user.get_id, CASE_TYPE)
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


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class CallCenterTestsSQL(CallCenterTests):
    """Run all tests in ``CallCenterTests`` with SQL backend
    """
    domain_name = "cc_test_sql"
    pass


class CallCenterSupervisorGroupTest(BaseCCTests):
    domain_name = 'cc_supervisor'

    def setUp(self):
        super(CallCenterSupervisorGroupTest, self).setUp()
        self.domain = create_domain(self.domain_name)
        self.supervisor = CommCareUser.create(self.domain_name, 'supervisor@' + self.domain_name, '***')

        self.supervisor_group = Group(
            domain=self.domain_name,
            name='supervisor group',
            case_sharing=True,
            users=[self.supervisor.get_id]
        )
        self.supervisor_group.save()

        self.domain.call_center_config.enabled = True
        self.domain.call_center_config.case_owner_id = self.supervisor_group.get_id
        self.domain.call_center_config.case_type = 'cc_flw'
        self.domain.save()

        self.user = CommCareUser.create(self.domain_name, 'user@' + self.domain_name, '***')
        sync_call_center_user_case(self.user)

        load_data(self.domain_name, self.user.user_id)

        # create one case of each type so that we get the indicators where there is no data for the period
        create_cases_for_types(self.domain_name, ['person', 'dog'])

    def tearDown(self):
        clear_data(self.domain.name)
        self.domain.delete()
        super(CallCenterSupervisorGroupTest, self).tearDown()

    @conditionally_run_with_all_backends
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
    domain_name = 'cc_sharing'

    def setUp(self):
        super(CallCenterCaseSharingTest, self).setUp()
        self.domain = create_domain(self.domain_name)
        self.supervisor = CommCareUser.create(self.domain_name, 'supervisor@' + self.domain_name, '***')

        self.domain.call_center_config.enabled = True
        self.domain.call_center_config.case_owner_id = self.supervisor.get_id
        self.domain.call_center_config.case_type = 'cc_flw'
        self.domain.save()

        self.user = CommCareUser.create(self.domain_name, 'user@' + self.domain_name, '***')
        sync_call_center_user_case(self.user)

        self.group = Group(
            domain=self.domain_name,
            name='case sharing group',
            case_sharing=True,
            users=[self.user.user_id]
        )
        self.group.save()

        load_data(
            self.domain_name,
            self.user.user_id,
            'not this user',
            self.group.get_id,
            case_opened_by=self.user.user_id,
            case_closed_by=self.user.user_id)

        # create one case of each type so that we get the indicators where there is no data for the period
        create_cases_for_types(self.domain_name, ['person', 'dog'])

    def tearDown(self):
        super(CallCenterCaseSharingTest, self).tearDown()
        clear_data(self.domain.name)
        self.domain.delete()

    @conditionally_run_with_all_backends
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
    domain_name = 'cc_opened_closed'

    def setUp(self):
        super(CallCenterTestOpenedClosed, self).setUp()
        self.domain = create_domain(self.domain_name)
        self.supervisor = CommCareUser.create(self.domain_name, 'supervisor@' + self.domain_name, '***')

        self.domain.call_center_config.enabled = True
        self.domain.call_center_config.case_owner_id = self.supervisor.get_id
        self.domain.call_center_config.case_type = 'cc_flw'
        self.domain.save()

        self.user = CommCareUser.create(self.domain_name, 'user@' + self.domain_name, '***')
        sync_call_center_user_case(self.user)

        load_data(self.domain_name, self.user.user_id, case_opened_by='not me', case_closed_by='not me')

        # create one case of each type so that we get the indicators where there is no data for the period
        create_cases_for_types(self.domain_name, ['person', 'dog'])

    def tearDown(self):
        super(CallCenterTestOpenedClosed, self).tearDown()
        clear_data(self.domain.name)
        self.domain.delete()

    @conditionally_run_with_all_backends
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


class TestSavingToUCRDatabase(BaseCCTests):
    domain_name = 'callcenterucrtest'

    def setUp(self):
        super(TestSavingToUCRDatabase, self).setUp()
        self.cc_domain, self.cc_user = create_domain_and_user(self.domain_name, 'user_ucr')
        create_cases_for_types(self.cc_domain.name, ['person', 'dog'])

        self.ucr_db_name = 'cchq_ucr_tests'
        db_conn_parts = settings.SQL_REPORTING_DATABASE_URL.split('/')
        db_conn_parts[-1] = self.ucr_db_name
        self.ucr_db_url = '/'.join(db_conn_parts)

        self.db_context = temporary_database(self.ucr_db_name)
        self.db_context.__enter__()

    def tearDown(self):
        super(TestSavingToUCRDatabase, self).tearDown()
        clear_data(self.cc_domain.name)
        self.cc_user.delete()
        self.cc_domain.delete()

        connection_manager.dispose_engine('ucr')
        self.db_context.__exit__(None, None, None)

    @conditionally_run_with_all_backends
    def test_standard_indicators(self):
        with override_settings(UCR_DATABASE_URL=self.ucr_db_url):
            load_data(self.cc_domain.name, self.cc_user.user_id)

            indicator_set = CallCenterIndicators(
                self.cc_domain.name,
                self.cc_domain.default_timezone,
                self.cc_domain.call_center_config.case_type,
                self.cc_user,
                custom_cache=locmem_cache
            )
            self._test_indicators(self.cc_user, indicator_set.get_data(), expected_standard_indicators())
