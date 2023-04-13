import datetime
from unittest.mock import Mock, patch

from django.db import IntegrityError
from django.http import Http404
from django.test import SimpleTestCase, TestCase

from dimagi.utils.dates import DateSpan

from corehq.apps.app_manager.const import (
    AMPLIFIES_NO,
    AMPLIFIES_NOT_SET,
    AMPLIFIES_YES,
)
from corehq.apps.app_manager.models import Application
from corehq.apps.data_analytics.malt_generator import (
    DEFAULT_EXPERIENCED_THRESHOLD,
    DEFAULT_MINIMUM_USE_THRESHOLD,
    MaltAppData,
    _build_malt_row_dict,
    _get_malt_app_data,
    _get_malt_row_dicts,
    _save_malt_row_dicts_to_db,
    _update_or_create_malt_row,
    generate_malt,
)
from corehq.apps.data_analytics.models import MALTRow
from corehq.apps.data_analytics.tests.utils import save_to_es_analytics_db
from corehq.apps.domain.models import Domain
from corehq.apps.es.forms import form_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.const import MISSING_APP_ID
from corehq.util.test_utils import disable_quickcache


@es_test(requires=[form_adapter])
class MaltGeneratorTest(TestCase):
    """
    End to end tests for malt generation. Use sparingly.
    """

    DOMAIN_NAME = "test"
    USERNAME = "malt-user"
    DEVICE_ID = "my_phone"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_domain()
        cls._setup_user()
        cls._setup_app()

    @classmethod
    def tearDownClass(cls):
        cls.user.delete(cls.domain.name, deleted_by=None)
        cls.domain.delete()
        super().tearDownClass()

    @classmethod
    def _setup_domain(cls):
        cls.domain = Domain(name=cls.DOMAIN_NAME)
        cls.domain.save()

    @classmethod
    def _setup_user(cls):
        cls.user = CommCareUser.create(cls.DOMAIN_NAME, cls.USERNAME, '*****', None, None)
        cls.user.save()

    @classmethod
    def _setup_app(cls):
        cls.app = Application.new_app(cls.DOMAIN_NAME, "app 1")
        cls.app.amplifies_workers = AMPLIFIES_YES
        cls.app.save()
        cls.app_id = cls.app._id

    def _save_form_data(self, app_id, received_on):
        save_to_es_analytics_db(
            domain=self.DOMAIN_NAME,
            received_on=received_on,
            device_id=self.DEVICE_ID,
            user_id=self.user._id,
            app_id=app_id,
        )

    def test_successfully_creates(self):
        self._save_form_data(self.app_id, datetime.datetime(2019, 12, 31))
        self._save_form_data(self.app_id, datetime.datetime(2020, 1, 1))
        self._save_form_data(self.app_id, datetime.datetime(2020, 1, 31))

        monthspan = DateSpan.from_month(1, 2020)
        generate_malt([monthspan], domains=[self.domain.name])
        malt_row = MALTRow.objects.get(
            user_id=self.user._id,
            app_id=self.app_id,
            device_id=self.DEVICE_ID,
            month=monthspan.startdate
        )
        self.assertEqual(malt_row.num_of_forms, 2)
        self.assertEqual(malt_row.wam, True)
        self.assertFalse(MALTRow.objects.filter(month=DateSpan.from_month(12, 2019).startdate).exists())

    def test_successfully_updates(self):
        self._save_form_data(self.app_id, datetime.datetime(2020, 1, 15))

        monthspan = DateSpan.from_month(1, 2020)
        generate_malt([monthspan], domains=[self.domain.name])

        malt_row = MALTRow.objects.get(user_id=self.user._id, app_id=self.app_id, device_id=self.DEVICE_ID,
                                       month=monthspan.startdate)

        self.assertEqual(malt_row.num_of_forms, 1)
        # hacky way to simulate last run date in between form submissions
        malt_row.last_run_date = datetime.datetime(2020, 1, 17)
        malt_row.save()

        self._save_form_data(self.app_id, datetime.datetime(2020, 1, 20))
        # mock bulk_create to avoid raising an actual error in the db transaction because this results in errors
        # when trying to make future changes within the same transaction
        with patch.object(MALTRow.objects, 'bulk_create', side_effect=IntegrityError):
            generate_malt([monthspan], domains=[self.domain.name])

        malt_row = MALTRow.objects.get(user_id=self.user._id, app_id=self.app_id, device_id=self.DEVICE_ID,
                                       month=monthspan.startdate)

        # ensure it updates
        self.assertEqual(malt_row.num_of_forms, 2)

    def test_does_not_update(self):
        self._save_form_data(self.app_id, datetime.datetime(2020, 1, 15))

        monthspan = DateSpan.from_month(1, 2020)
        generate_malt([monthspan], domains=[self.domain.name])

        malt_row = MALTRow.objects.get(
            user_id=self.user._id,
            app_id=self.app_id,
            device_id=self.DEVICE_ID,
            month=monthspan.startdate
        )
        previous_run_date = malt_row.last_run_date

        generate_malt([monthspan], domains=[self.domain.name])

        malt_row = MALTRow.objects.get(
            user_id=self.user._id,
            app_id=self.app_id,
            device_id=self.DEVICE_ID,
            month=monthspan.startdate
        )
        self.assertEqual(malt_row.last_run_date, previous_run_date)

    def test_multiple_months(self):
        self._save_form_data(self.app_id, datetime.datetime(2019, 12, 15))
        self._save_form_data(self.app_id, datetime.datetime(2020, 1, 15))
        self._save_form_data(self.app_id, datetime.datetime(2020, 1, 16))

        monthspans = [DateSpan.from_month(12, 2019), DateSpan.from_month(1, 2020)]
        generate_malt(monthspans, domains=[self.domain.name])

        december_malt = MALTRow.objects.get(domain_name=self.domain, month=DateSpan.from_month(12, 2019).startdate)
        january_malt = MALTRow.objects.get(domain_name=self.domain, month=DateSpan.from_month(1, 2020).startdate)

        self.assertEqual(december_malt.num_of_forms, 1)
        self.assertEqual(january_malt.num_of_forms, 2)


class TestSaveMaltRowDictsToDB(TestCase):

    def test_successful_bulk_create(self):
        malt_row_dicts = [
            create_malt_row_dict({'domain': 'domain1'}),
            create_malt_row_dict({'domain': 'domain2'}),
        ]
        with patch('corehq.apps.data_analytics.malt_generator._update_or_create_malt_row') as mock_updateorcreate:
            _save_malt_row_dicts_to_db(malt_row_dicts)

        mock_updateorcreate.assert_not_called()

    def test_update_or_create_called_if_integrity_error(self):
        """
        Ideally could avoid mocking _update_or_create_malt_row to ensure this recovers from an IntegrityError, but
        because this test runs inside one transaction the IntegrityError corrupts the transaction.

        An alternative is to subclass TransactionTestCase which implements a different rollback strategy, but this
        ran too slowly to be worth it. See TestUpdateOrCreateMaltRow to be reassured _update_or_create_malt_row
        works properly.
        """
        malt_row_dict = create_malt_row_dict({'domain': 'test-domain', 'num_of_forms': 25})
        # pre-save the object to force integrity error in bulk create
        MALTRow.objects.create(**malt_row_dict)
        with patch('corehq.apps.data_analytics.malt_generator._update_or_create_malt_row') as mock_updateorcreate:
            _save_malt_row_dicts_to_db([malt_row_dict])

        mock_updateorcreate.assert_called()


class TestUpdateOrCreateMaltRow(TestCase):

    def setUp(self):
        super().setUp()
        self.malt_row_dict = create_malt_row_dict({'domain': 'test-domain', 'num_of_forms': 25})

    def test_successful_create(self):

        _update_or_create_malt_row(self.malt_row_dict)

        rows = MALTRow.objects.filter(domain_name='test-domain')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].num_of_forms, 25)

    def test_successful_update(self):
        MALTRow.objects.create(**self.malt_row_dict)
        rows = MALTRow.objects.filter(domain_name='test-domain')
        self.assertEqual(rows[0].num_of_forms, 25)
        updated_malt_row_dict = create_malt_row_dict({'domain': 'test-domain', 'num_of_forms': 50})

        _update_or_create_malt_row(updated_malt_row_dict)

        rows = MALTRow.objects.filter(domain_name='test-domain')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].num_of_forms, 50)


@disable_quickcache
class TestGetMaltAppData(SimpleTestCase):

    def setUp(self) -> None:
        super().setUp()
        self.default_app_data = create_malt_app_data()

    def test_returns_default_app_data_if_no_app_id(self):
        actual_app_data = _get_malt_app_data('domain', None)
        self.assertEqual(actual_app_data, self.default_app_data)

    def test_returns_default_app_data_if_get_app_raises_Http404(self):
        with patch('corehq.apps.data_analytics.malt_generator.get_app') as mock_getapp:
            mock_getapp.side_effect = Http404
            actual_app_data = _get_malt_app_data('domain', 'app_id')
        self.assertEqual(actual_app_data, self.default_app_data)

    def test_returns_expected_app_data(self):
        app = Application(
            amplifies_workers='yes',
            amplifies_project='no',
            minimum_use_threshold='1',
            experienced_threshold='10',
        )

        with patch('corehq.apps.data_analytics.malt_generator.get_app', return_value=app):
            actual_app_data = _get_malt_app_data('domain', 'app_id')

        self.assertEqual(actual_app_data, MaltAppData('yes', 'no', '1', '10', False))

    def test_returns_expected_app_data_if_deleted(self):
        app = Application(
            amplifies_workers='yes',
            amplifies_project='no',
            minimum_use_threshold='1',
            experienced_threshold='10',
        )
        app.doc_type = 'Application-Deleted'

        with patch('corehq.apps.data_analytics.malt_generator.get_app', return_value=app):
            actual_app_data = _get_malt_app_data('domain', 'app_id')

        self.assertEqual(actual_app_data, MaltAppData('yes', 'no', '1', '10', True))


class TestBuildMaltRowDict(SimpleTestCase):

    def setUp(self):
        super().setUp()
        self.domain = 'domain'
        self.monthspan = DateSpan.from_month(1, 2022)
        self.run_date = self.monthspan.computed_enddate
        self.app_row = create_mock_nested_query_row()
        self.user = create_user_for_malt_tests(is_web_user=True)
        self.app_data = create_malt_app_data()

        app_data_patcher = patch('corehq.apps.data_analytics.malt_generator._get_malt_app_data')
        self.mock_get_malt_app_data = app_data_patcher.start()
        self.mock_get_malt_app_data.return_value = self.app_data
        self.addCleanup(app_data_patcher.stop)

    def test_returns_expected_value_for_month(self):
        self.monthspan = DateSpan.from_month(3, 2020)

        actual_malt_row_dict = _build_malt_row_dict(
            self.app_row, self.domain, self.user, self.monthspan, self.run_date
        )

        self.assertEqual(actual_malt_row_dict['month'], datetime.datetime(2020, 3, 1, 0, 0))

    def test_app_id_set_to_missing_if_none(self):
        self.app_row.app_id = None

        actual_malt_row_dict = _build_malt_row_dict(
            self.app_row, self.domain, self.user, self.monthspan, self.run_date
        )

        self.assertEqual(actual_malt_row_dict['app_id'], MISSING_APP_ID)

    def test_wam_and_pam_values_of_not_set_map_to_none(self):
        app_data = create_malt_app_data(wam=AMPLIFIES_NOT_SET, pam=AMPLIFIES_NOT_SET)
        self.mock_get_malt_app_data.return_value = app_data

        actual_malt_row_dict = _build_malt_row_dict(
            self.app_row, self.domain, self.user, self.monthspan, self.run_date
        )

        self.assertEqual(actual_malt_row_dict['wam'], None)
        self.assertEqual(actual_malt_row_dict['pam'], None)

    def test_wam_and_pam_values_of_yes_map_to_true(self):
        app_data = create_malt_app_data(wam=AMPLIFIES_YES, pam=AMPLIFIES_YES)
        self.mock_get_malt_app_data.return_value = app_data

        actual_malt_row_dict = _build_malt_row_dict(
            self.app_row, self.domain, self.user, self.monthspan, self.run_date
        )

        self.assertEqual(actual_malt_row_dict['wam'], True)
        self.assertEqual(actual_malt_row_dict['pam'], True)

    def test_wam_and_pam_values_of_no_map_to_false(self):
        app_data = create_malt_app_data(wam=AMPLIFIES_NO, pam=AMPLIFIES_NO)
        self.mock_get_malt_app_data.return_value = app_data

        actual_malt_row_dict = _build_malt_row_dict(
            self.app_row, self.domain, self.user, self.monthspan, self.run_date
        )

        self.assertEqual(actual_malt_row_dict['wam'], False)
        self.assertEqual(actual_malt_row_dict['pam'], False)

    def test_user_type_for_web_user(self):
        actual_malt_row_dict = _build_malt_row_dict(
            self.app_row, self.domain, self.user, self.monthspan, self.run_date
        )

        self.assertEqual(actual_malt_row_dict['user_type'], 'WebUser')

    def test_user_type_for_mobile_user(self):
        self.user = create_user_for_malt_tests(is_web_user=False)

        actual_malt_row_dict = _build_malt_row_dict(
            self.app_row, self.domain, self.user, self.monthspan, self.run_date
        )

        self.assertEqual(actual_malt_row_dict['user_type'], 'CommCareUser')


class TestGetMaltRowDicts(SimpleTestCase):

    def setUp(self) -> None:
        super().setUp()
        self.domain = 'domain'
        self.monthspan = DateSpan.from_month(1, 2022)
        self.run_date = self.monthspan.computed_enddate
        self.web_user = create_user_for_malt_tests(is_web_user=True, user_id='user_id_1', username='user1')
        self.mobile_user = create_user_for_malt_tests(is_web_user=False, user_id='user_id_2', username='user2')
        self.app_data = create_malt_app_data()
        self.users_by_id = {'user_id_1': self.web_user, 'user_id_2': self.mobile_user}

        app_data_patcher = patch('corehq.apps.data_analytics.malt_generator._get_malt_app_data')
        self.mock_get_malt_app_data = app_data_patcher.start()
        self.mock_get_malt_app_data.return_value = self.app_data
        self.addCleanup(app_data_patcher.stop)

        breakdown_es_patcher = patch('corehq.apps.data_analytics.malt_generator.get_app_submission_breakdown_es')
        self.mock_app_submission_breakdown = breakdown_es_patcher.start()
        self.mock_app_submission_breakdown.return_value = [
            create_mock_nested_query_row(user_id='user_id_1'),
            create_mock_nested_query_row(user_id='user_id_2'),
        ]
        self.addCleanup(breakdown_es_patcher.stop)

    def test_num_of_forms(self):
        self.mock_app_submission_breakdown.return_value = [
            create_mock_nested_query_row(user_id='user_id_1', doc_count=50),
            create_mock_nested_query_row(user_id='user_id_2', doc_count=25),
        ]

        malt_row_dicts = _get_malt_row_dicts(
            self.domain, self.monthspan, self.users_by_id, self.run_date
        )

        user1_malt_row_dict = malt_row_dicts[0]
        user2_malt_row_dict = malt_row_dicts[1]
        self.assertEqual(user1_malt_row_dict['num_of_forms'], 50)
        self.assertEqual(user2_malt_row_dict['num_of_forms'], 25)


def create_malt_app_data(wam=AMPLIFIES_NOT_SET,
                         pam=AMPLIFIES_NOT_SET,
                         use_threshold=DEFAULT_MINIMUM_USE_THRESHOLD,
                         experienced_threshold=DEFAULT_EXPERIENCED_THRESHOLD,
                         is_app_deleted=False):
    return MaltAppData(wam, pam, use_threshold, experienced_threshold, is_app_deleted)


def create_user_for_malt_tests(is_web_user=True, user_id='user_id', username='username'):
    user = WebUser() if is_web_user else CommCareUser()
    user._id = user_id
    user.username = username
    user.email = 'email'
    return user


def create_mock_nested_query_row(user_id='user_id', app_id='abc123', device_id='web', doc_count=10):
    # NestedQueryRow is the ElasticSearch class this is mocking
    mock_nested_query_row = Mock()
    mock_nested_query_row.app_id = app_id
    mock_nested_query_row.device_id = device_id
    mock_nested_query_row.user_id = user_id
    mock_nested_query_row.doc_count = doc_count
    return mock_nested_query_row


def create_malt_row_dict(data):
    return {
        'month': data.get('month', datetime.datetime(2022, 1, 1, 0, 0)),
        'user_id': data.get('user_id', 'test-user-id'),
        'username': data.get('username', 'test-username'),
        'email': data.get('email', 'test-email'),
        'user_type': data.get('user_type', 'test-user-type'),
        'domain_name': data.get('domain', 'test-domain'),
        'num_of_forms': data.get('num_of_forms', 0),
        'app_id': data.get('app_id', MISSING_APP_ID),
        'device_id': data.get('device_id', 'web'),
        'wam': data.get('wam', None),
        'pam': data.get('pam', None),
        'use_threshold': data.get('use_threshold', DEFAULT_MINIMUM_USE_THRESHOLD),
        'experienced_threshold': data.get('experienced_threshold', DEFAULT_EXPERIENCED_THRESHOLD),
        'is_app_deleted': data.get('is_app_deleted', False),
    }
