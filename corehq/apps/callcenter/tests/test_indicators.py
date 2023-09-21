import uuid
from collections import namedtuple
from unittest.mock import patch

from django.core import cache
from django.db import DEFAULT_DB_ALIAS
from django.test import TestCase

from corehq.apps.callcenter.const import (
    DATE_RANGES,
    MONTH0,
    MONTH1,
    WEEK0,
    WEEK1,
)
from corehq.apps.callcenter.indicator_sets import (
    AAROHI_MOTHER_FORM,
    CachedIndicators,
    CallCenterIndicators,
    cache_key,
)
from corehq.apps.callcenter.models import (
    CallCenterIndicatorConfig,
    TypedIndicator,
)
from corehq.apps.callcenter.tests.sql_fixture import (
    clear_data,
    load_custom_data,
    load_data,
)
from corehq.apps.callcenter.utils import CallCenterCase
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.groups.models import Group
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.models import CommCareCase
from corehq.form_processor.tests.utils import sharded
from corehq.sql_db.connections import connection_manager, override_engine
from corehq.sql_db.tests.utils import temporary_database

CASE_TYPE = 'cc_flw'

locmem_cache = cache.caches['locmem']


def create_domain_and_user(domain_name, username):
    domain = create_domain(domain_name)
    user = CommCareUser.get_by_username(username)
    if user:
        user.delete(domain_name, deleted_by=None)

    user_id = str(uuid.uuid4())
    domain.call_center_config.enabled = True
    domain.call_center_config.case_owner_id = user_id
    domain.call_center_config.case_type = CASE_TYPE
    domain.save()

    user = CommCareUser.create(domain_name, username, '***', None, None, uuid=user_id)
    return domain, user


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


def expected_standard_indicators(
        no_data=False, include_legacy=True, include_totals=True, case_types=None, limit_ranges=None):
    case_types = case_types if case_types is not None else ['person', 'dog']
    expected = {}
    expected_values = []
    if include_totals:
        expected_values.extend([
            StaticIndicators('forms_submitted', [2, 4, 7, 0], False, None),
            StaticIndicators('cases_total', [4, 4, 6, 5], False, None),
            StaticIndicators('cases_opened', [0, 1, 3, 5], False, None),
            StaticIndicators('cases_closed', [0, 0, 2, 2], False, None),
            StaticIndicators('cases_active', [0, 1, 3, 5], False, None),
        ])

    if 'dog' in case_types:
        expected_values.extend([
            StaticIndicators('cases_total', [3, 3, 3, 5], False, 'dog'),
            StaticIndicators('cases_opened', [0, 0, 0, 5], False, 'dog'),
            StaticIndicators('cases_closed', [0, 0, 0, 2], False, 'dog'),
            StaticIndicators('cases_active', [0, 0, 0, 5], False, 'dog')
        ])

    if 'person' in case_types:
        expected_values.extend([
            StaticIndicators('cases_total', [1, 1, 3, 0], False, 'person'),
            StaticIndicators('cases_opened', [0, 1, 3, 0], False, 'person'),
            StaticIndicators('cases_closed', [0, 0, 2, 0], False, 'person'),
            StaticIndicators('cases_active', [0, 1, 3, 0], False, 'person'),
        ])

    if include_legacy:
        expected_values.extend([
            StaticIndicators('formsSubmitted', [2, 4, 7, 0], True, None),
            StaticIndicators('casesUpdated', [0, 1, 3, 5], True, None),
        ])

        expected['totalCases'] = 0 if no_data else 5

    for val in expected_values:
        values = [0] * 4 if no_data else val.values
        expected.update(get_indicators(val.name, values, val.infix, val.is_legacy, limit_ranges))

    return expected


class BaseCCTests(TestCase):
    domain_name = None

    def setUp(self):
        super(BaseCCTests, self).setUp()
        locmem_cache.clear()

    def tearDown(self):
        super(BaseCCTests, self).tearDown()

    def _test_indicators(self, user, data_set, expected):
        user_case = CommCareCase.objects.get_case_by_external_id(user.domain, user.user_id, CASE_TYPE)
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
            self.fail('Additional indicators:\n{}'.format('\t\n'.join(list(user_data))))


@patch('corehq.apps.callcenter.indicator_sets.get_case_types_for_domain_es',
       return_value={'person', 'dog', CASE_TYPE})
class CallCenterTests(BaseCCTests):
    domain_name = 'callcentertest'

    @classmethod
    def setUpClass(cls):
        super(CallCenterTests, cls).setUpClass()
        cls.cc_domain, cls.cc_user = create_domain_and_user(cls.domain_name, 'user1')
        load_data(cls.cc_domain.name, cls.cc_user.user_id)
        cls.cc_user_no_data = CommCareUser.create(cls.cc_domain.name, 'user3', '***', None, None)

        cls.aarohi_domain, cls.aarohi_user = create_domain_and_user('aarohi', 'user2')
        load_custom_data(cls.aarohi_domain.name, cls.aarohi_user.user_id, xmlns=AAROHI_MOTHER_FORM)

    @classmethod
    def tearDownClass(cls):
        clear_data(cls.aarohi_domain.name)
        clear_data(cls.cc_domain.name)
        cls.cc_user.delete(cls.cc_domain.name, deleted_by=None)
        cls.cc_user_no_data.delete(cls.cc_domain.name, deleted_by=None)
        cls.cc_domain.delete()
        cls.aarohi_user.delete(cls.aarohi_domain.name, deleted_by=None)
        cls.aarohi_domain.delete()
        super(CallCenterTests, cls).tearDownClass()

    def check_cc_indicators(self, data_set, expected):
        self._test_indicators(self.cc_user, data_set, expected)
        expected_no_data = expected_standard_indicators(no_data=True)
        self._test_indicators(self.cc_user_no_data, data_set, expected_no_data)

    def test_standard_indicators(self, mock):
        indicator_set = CallCenterIndicators(
            self.cc_domain.name,
            self.cc_domain.default_timezone,
            self.cc_domain.call_center_config.case_type,
            self.cc_user,
            custom_cache=locmem_cache
        )
        self.assertEqual(
            set(indicator_set.user_to_case_map),
            set([self.cc_user.get_id, self.cc_user_no_data.get_id])
        )
        self.assertEqual(
            indicator_set.users_needing_data, set([self.cc_user.get_id, self.cc_user_no_data.get_id])
        )
        self.assertEqual(
            indicator_set.owners_needing_data, set([self.cc_user.get_id, self.cc_user_no_data.get_id])
        )
        self.check_cc_indicators(indicator_set.get_data(), expected_standard_indicators())

    def test_standard_indicators_no_legacy(self, mock):
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

    def test_standard_indicators_case_totals_only(self, mock):
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

    def test_standard_indicators_case_dog_only(self, mock):
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

    def test_standard_indicators_case_week1_only(self, mock):
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

    def test_sync_log(self, mock):
        user_case = CommCareCase.objects.get_case_by_external_id(
            self.cc_domain.name, self.cc_user.get_id, CASE_TYPE)
        indicator_set = CallCenterIndicators(
            self.cc_domain.name,
            self.cc_domain.default_timezone,
            self.cc_domain.call_center_config.case_type,
            self.cc_user,
            custom_cache=locmem_cache,
            override_cases=[CallCenterCase.from_case(user_case)]
        )
        self.assertEqual(list(indicator_set.user_to_case_map), [self.cc_user.get_id])
        self.assertEqual(indicator_set.users_needing_data, set([self.cc_user.get_id]))
        self.assertEqual(indicator_set.owners_needing_data, set([self.cc_user.get_id]))
        self._test_indicators(self.cc_user, indicator_set.get_data(), expected_standard_indicators())

    def test_custom_indicators(self, mock):
        mock.return_value = set()
        expected = {'totalCases': 0}
        expected.update(get_indicators('formsSubmitted', [3, 3, 9, 0], is_legacy=True))
        expected.update(get_indicators('forms_submitted', [3, 3, 9, 0]))
        expected.update(get_indicators('casesUpdated', [0, 0, 0, 0], is_legacy=True))
        expected.update(get_indicators('cases_total', [0, 0, 0, 0]))
        expected.update(get_indicators('cases_opened', [0, 0, 0, 0]))
        expected.update(get_indicators('cases_closed', [0, 0, 0, 0]))
        expected.update(get_indicators('cases_active', [0, 0, 0, 0]))

        # custom
        expected.update(get_indicators('motherForms', [3, 3, 9, 0], is_legacy=True))
        expected.update(get_indicators('childForms', [0, 0, 0, 0], is_legacy=True))
        expected.update(get_indicators('motherDuration', [3, 4, 4, 0], is_legacy=True))

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

    def test_custom_indicators_limited(self, mock):
        expected = {}

        # custom
        expected.update(
            get_indicators('motherForms', [3, None, 9, None], is_legacy=True, limit_ranges=[WEEK0, MONTH0])
        )
        expected.update(
            get_indicators('childForms', [None, 0, None, None], is_legacy=True, limit_ranges=[WEEK1])
        )
        expected.update(
            get_indicators('motherDuration', [None, None, None, 0], is_legacy=True, limit_ranges=[MONTH1])
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

    def test_caching(self, mock):
        user_case = CommCareCase.objects.get_case_by_external_id(
            self.cc_domain.name, self.cc_user.get_id, CASE_TYPE)
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
            set(indicator_set.user_to_case_map),
            set([self.cc_user.get_id, self.cc_user_no_data.get_id])
        )
        self.assertEqual(indicator_set.users_needing_data, set([self.cc_user_no_data.get_id]))
        self.assertEqual(indicator_set.owners_needing_data, set([self.cc_user_no_data.get_id]))
        self.check_cc_indicators(indicator_set.get_data(), expected_indicators)

    def test_no_cases_owned_by_user(self, mock):
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
        self.assertEqual(list(indicator_set.user_to_case_map), [])
        self.assertEqual(indicator_set.users_needing_data, set())
        self.assertEqual(indicator_set.owners_needing_data, set())
        self.assertEqual(indicator_set.get_data(), {})


class CallCenterSupervisorGroupTest(BaseCCTests):
    domain_name = 'cc_supervisor'

    def setUp(self):
        super(CallCenterSupervisorGroupTest, self).setUp()
        self.domain = create_domain(self.domain_name)
        self.supervisor = CommCareUser.create(self.domain_name, 'supervisor@' + self.domain_name, '***',
                                              None, None)

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

        self.user = CommCareUser.create(self.domain_name, 'user@' + self.domain_name, '***', None, None)

        load_data(self.domain_name, self.user.user_id)

    def tearDown(self):
        clear_data(self.domain.name)
        self.domain.delete()
        super(CallCenterSupervisorGroupTest, self).tearDown()

    @patch('corehq.apps.callcenter.indicator_sets.get_case_types_for_domain_es',
           return_value={'person', 'dog', CASE_TYPE})
    def test_users_assigned_via_group(self, mock):
        # Ensure that users who are assigned to the supervisor via a group are also included
        # in final data set.
        indicator_set = CallCenterIndicators(
            self.domain.name,
            self.domain.default_timezone,
            self.domain.call_center_config.case_type,
            self.supervisor,
            custom_cache=locmem_cache
        )
        self.assertEqual(list(indicator_set.user_to_case_map), [self.user.get_id])
        self.assertEqual(indicator_set.users_needing_data, set([self.user.get_id]))
        self.assertEqual(indicator_set.owners_needing_data, set([self.user.get_id]))
        self._test_indicators(self.user, indicator_set.get_data(), expected_standard_indicators())


class CallCenterCaseSharingTest(BaseCCTests):
    domain_name = 'cc_sharing'

    def setUp(self):
        super(CallCenterCaseSharingTest, self).setUp()
        self.domain = create_domain(self.domain_name)
        self.supervisor = CommCareUser.create(self.domain_name, 'supervisor@' + self.domain_name, '***',
                                              None, None)

        self.domain.call_center_config.enabled = True
        self.domain.call_center_config.case_owner_id = self.supervisor.get_id
        self.domain.call_center_config.case_type = 'cc_flw'
        self.domain.save()

        self.user = CommCareUser.create(self.domain_name, 'user@' + self.domain_name, '***', None, None)

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

    def tearDown(self):
        super(CallCenterCaseSharingTest, self).tearDown()
        clear_data(self.domain.name)
        self.domain.delete()

    @patch('corehq.apps.callcenter.indicator_sets.get_case_types_for_domain_es',
           return_value={'person', 'dog', CASE_TYPE})
    def test_cases_owned_by_group(self, mock):
        # Ensure that indicators include cases owned by a case sharing group the user is part of.
        indicator_set = CallCenterIndicators(
            self.domain.name,
            self.domain.default_timezone,
            self.domain.call_center_config.case_type,
            self.supervisor,
            custom_cache=locmem_cache
        )
        self.assertEqual(list(indicator_set.user_to_case_map), [self.user.get_id])
        self.assertEqual(indicator_set.users_needing_data, set([self.user.get_id]))
        self.assertEqual(indicator_set.owners_needing_data, set([self.user.get_id, self.group.get_id]))
        expected = expected_standard_indicators()
        expected['totalCases'] = 0  # no cases with user_id = self.user.get_id
        self._test_indicators(self.user, indicator_set.get_data(), expected)


class CallCenterTestOpenedClosed(BaseCCTests):
    domain_name = 'cc_opened_closed'

    def setUp(self):
        super(CallCenterTestOpenedClosed, self).setUp()
        self.domain = create_domain(self.domain_name)
        self.supervisor = CommCareUser.create(self.domain_name, 'supervisor@' + self.domain_name, '***',
                                              None, None)

        self.domain.call_center_config.enabled = True
        self.domain.call_center_config.case_owner_id = self.supervisor.get_id
        self.domain.call_center_config.case_type = 'cc_flw'
        self.domain.save()

        self.user = CommCareUser.create(self.domain_name, 'user@' + self.domain_name, '***', None, None)

        load_data(self.domain_name, self.user.user_id, case_opened_by='not me', case_closed_by='not me')

    def tearDown(self):
        super(CallCenterTestOpenedClosed, self).tearDown()
        clear_data(self.domain.name)
        self.domain.delete()

    @patch('corehq.apps.callcenter.indicator_sets.get_case_types_for_domain_es',
           return_value={'person', 'dog', CASE_TYPE})
    def test_opened_closed(self, mock):
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
                expected[key] = 0
        self._test_indicators(self.user, indicator_set.get_data(), expected)


@sharded
class TestSavingToUCRDatabase(BaseCCTests):
    domain_name = 'callcenterucrtest'

    def setUp(self):
        super(TestSavingToUCRDatabase, self).setUp()
        self.cc_domain, self.cc_user = create_domain_and_user(self.domain_name, 'user_ucr')

        self.ucr_db_name = 'cchq_ucr_tests'
        db_conn_parts = connection_manager.get_connection_string(DEFAULT_DB_ALIAS).split('/')
        db_conn_parts[-1] = self.ucr_db_name
        self.ucr_db_url = '/'.join(db_conn_parts)

        self.db_context = temporary_database(self.ucr_db_name)
        self.db_context.__enter__()

    def tearDown(self):
        super(TestSavingToUCRDatabase, self).tearDown()
        clear_data(self.cc_domain.name)
        self.cc_user.delete(self.cc_domain.name, deleted_by=None)
        self.cc_domain.delete()

        connection_manager.dispose_engine('ucr')
        self.db_context.__exit__(None, None, None)

    @patch('corehq.apps.callcenter.indicator_sets.get_case_types_for_domain_es',
           return_value={'person', 'dog', CASE_TYPE})
    def test_standard_indicators(self, mock):
        with override_engine('ucr', self.ucr_db_url):
            load_data(self.cc_domain.name, self.cc_user.user_id)

            indicator_set = CallCenterIndicators(
                self.cc_domain.name,
                self.cc_domain.default_timezone,
                self.cc_domain.call_center_config.case_type,
                self.cc_user,
                custom_cache=locmem_cache
            )
            self._test_indicators(self.cc_user, indicator_set.get_data(), expected_standard_indicators())
