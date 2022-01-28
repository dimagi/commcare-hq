import datetime
from unittest.mock import Mock, patch

from django.http import Http404
from django.test import SimpleTestCase, TestCase

from dimagi.utils.dates import DateSpan
from pillowtop.es_utils import initialize_index_and_mapping

from corehq.apps.app_manager.const import (
    AMPLIFIES_NO,
    AMPLIFIES_NOT_SET,
    AMPLIFIES_YES,
)
from corehq.apps.app_manager.models import Application
from corehq.apps.data_analytics.const import NOT_SET, YES
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
from corehq.apps.es.tests.utils import es_test
from corehq.apps.smsforms.app import COMMCONNECT_DEVICE_ID
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.const import MISSING_APP_ID
from corehq.elastic import get_es_new
from corehq.pillows.mappings.xform_mapping import XFORM_INDEX_INFO
from corehq.util.elastic import ensure_index_deleted
from corehq.util.test_utils import disable_quickcache


@es_test
class MaltGeneratorTest(TestCase):

    DOMAIN_NAME = "test"
    USERNAME = "malt-user"
    DEVICE_ID = "my_phone"
    UNKNOWN_ID = "UNKNOWN_ID"

    correct_date = datetime.datetime.now()
    out_of_range_date = correct_date - datetime.timedelta(days=32)
    malt_month = DateSpan.from_month(correct_date.month, correct_date.year)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.es = get_es_new()
        ensure_index_deleted(XFORM_INDEX_INFO.index)
        initialize_index_and_mapping(cls.es, XFORM_INDEX_INFO)
        cls._setup_domain_user()
        cls._setup_apps()
        cls._setup_forms()
        cls.es.indices.refresh(XFORM_INDEX_INFO.index)
        cls.run_malt_generation()

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()
        MALTRow.objects.all().delete()
        ensure_index_deleted(XFORM_INDEX_INFO.index)
        super().tearDownClass()

    @classmethod
    def _setup_domain_user(cls):
        cls.domain = Domain(name=cls.DOMAIN_NAME)
        cls.domain.save()
        cls.user = CommCareUser.create(cls.DOMAIN_NAME, cls.USERNAME, '*****', None, None)
        cls.user.save()
        cls.user_id = cls.user._id

    @classmethod
    def _setup_apps(cls):
        cls.non_wam_app = Application.new_app(cls.DOMAIN_NAME, "app 1")
        cls.wam_app = Application.new_app(cls.DOMAIN_NAME, "app 2")
        cls.wam_app.amplifies_workers = AMPLIFIES_YES
        cls.non_wam_app.save()
        cls.wam_app.save()
        cls.non_wam_app_id = cls.non_wam_app._id
        cls.wam_app_id = cls.wam_app._id

    @classmethod
    def _setup_forms(cls):
        def _save_form_data(app_id, received_on=cls.correct_date, device_id=cls.DEVICE_ID):
            save_to_es_analytics_db(
                domain=cls.DOMAIN_NAME,
                received_on=received_on,
                device_id=device_id,
                user_id=cls.user_id,
                app_id=app_id,
            )

        def _save_multiple_forms(app_ids, received_on):
            for app_id in app_ids:
                _save_form_data(app_id, received_on=received_on)

        out_of_range_form_apps = [
            cls.non_wam_app_id,
            cls.wam_app_id,
        ]
        in_range_form_apps = [
            # should be included in MALT
            cls.non_wam_app_id,
            cls.non_wam_app_id,
            cls.non_wam_app_id,
            cls.wam_app_id,
            cls.wam_app_id,
            # should be included in MALT
            '',
        ]

        _save_multiple_forms(out_of_range_form_apps, cls.out_of_range_date)
        _save_multiple_forms(in_range_form_apps, cls.correct_date)

        # should be included in MALT
        _save_form_data(cls.non_wam_app_id, device_id=COMMCONNECT_DEVICE_ID)

    @classmethod
    def run_malt_generation(cls):
        generate_malt([cls.malt_month])

    def _assert_malt_row_exists(self, query_filters):
        rows = MALTRow.objects.filter(username=self.USERNAME, **query_filters)
        self.assertEqual(rows.count(), 1)

    def test_wam_yes_malt_counts(self):
        # 2 forms for WAM.YES app
        self._assert_malt_row_exists({
            'app_id': self.wam_app_id,
            'num_of_forms': 2,
            'wam': YES,
        })

    def test_wam_not_set_malt_counts(self):
        # 3 forms from self.DEVICE_ID for WAM not-set app
        self._assert_malt_row_exists({
            'app_id': self.non_wam_app_id,
            'num_of_forms': 3,
            'wam': NOT_SET,
            'device_id': self.DEVICE_ID,
        })

        # 1 form from COMMONCONNECT_DEVICE_ID for WAM not-set app
        self._assert_malt_row_exists({
            'app_id': self.non_wam_app_id,
            'num_of_forms': 1,
            'wam': NOT_SET,
            'device_id': COMMCONNECT_DEVICE_ID,
        })

    def test_missing_app_id_is_included(self):
        # apps with MISSING_APP_ID should be included in MALT
        self._assert_malt_row_exists({
            'app_id': MISSING_APP_ID,
            'num_of_forms': 1,
            'wam': NOT_SET,
        })


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
        self.app_row = create_mock_nested_query_row()
        self.user = create_user_for_malt_tests(is_web_user=True)
        self.app_data = create_malt_app_data()

        self.patcher = patch('corehq.apps.data_analytics.malt_generator._get_malt_app_data')
        self.mock_get_malt_app_data = self.patcher.start()
        self.mock_get_malt_app_data.return_value = self.app_data

    def tearDown(self):
        self.patcher.stop()
        super().tearDown()

    def test_returns_expected_value_for_month(self):
        monthspan = DateSpan.from_month(3, 2020)

        actual_malt_row_dict = _build_malt_row_dict(self.app_row, self.domain, self.user, monthspan)

        self.assertEqual(actual_malt_row_dict['month'], datetime.datetime(2020, 3, 1, 0, 0))

    def test_app_id_set_to_missing_if_none(self):
        self.app_row.app_id = None

        actual_malt_row_dict = _build_malt_row_dict(self.app_row, self.domain, self.user, self.monthspan)

        self.assertEqual(actual_malt_row_dict['app_id'], '_MISSING_APP_ID')

    def test_wam_and_pam_values_of_not_set_map_to_none(self):
        app_data = create_malt_app_data(wam=AMPLIFIES_NOT_SET, pam=AMPLIFIES_NOT_SET)
        self.mock_get_malt_app_data.return_value = app_data

        actual_malt_row_dict = _build_malt_row_dict(self.app_row, self.domain, self.user, self.monthspan)

        self.assertEqual(actual_malt_row_dict['wam'], None)
        self.assertEqual(actual_malt_row_dict['pam'], None)

    def test_wam_and_pam_values_of_yes_map_to_true(self):
        app_data = create_malt_app_data(wam=AMPLIFIES_YES, pam=AMPLIFIES_YES)
        self.mock_get_malt_app_data.return_value = app_data

        actual_malt_row_dict = _build_malt_row_dict(self.app_row, self.domain, self.user, self.monthspan)

        self.assertEqual(actual_malt_row_dict['wam'], True)
        self.assertEqual(actual_malt_row_dict['pam'], True)

    def test_wam_and_pam_values_of_no_map_to_false(self):
        app_data = create_malt_app_data(wam=AMPLIFIES_NO, pam=AMPLIFIES_NO)
        self.mock_get_malt_app_data.return_value = app_data

        actual_malt_row_dict = _build_malt_row_dict(self.app_row, self.domain, self.user, self.monthspan)

        self.assertEqual(actual_malt_row_dict['wam'], False)
        self.assertEqual(actual_malt_row_dict['pam'], False)

    def test_user_type_for_web_user(self):
        actual_malt_row_dict = _build_malt_row_dict(self.app_row, self.domain, self.user, self.monthspan)

        self.assertEqual(actual_malt_row_dict['user_type'], 'WebUser')

    def test_user_type_for_mobile_user(self):
        self.user = create_user_for_malt_tests(is_web_user=False)

        actual_malt_row_dict = _build_malt_row_dict(self.app_row, self.domain, self.user, self.monthspan)

        self.assertEqual(actual_malt_row_dict['user_type'], 'CommCareUser')


class TestGetMaltRowDicts(SimpleTestCase):

    def setUp(self) -> None:
        super().setUp()
        self.domain = 'domain'
        self.monthspan = DateSpan.from_month(1, 2022)
        self.web_user = create_user_for_malt_tests(is_web_user=True, user_id='user_id_1', username='user1')
        self.mobile_user = create_user_for_malt_tests(is_web_user=False, user_id='user_id_2', username='user2')
        self.app_data = create_malt_app_data()

        self.patcher = patch('corehq.apps.data_analytics.malt_generator._get_malt_app_data')
        self.mock_get_malt_app_data = self.patcher.start()
        self.mock_get_malt_app_data.return_value = self.app_data

    def tearDown(self):
        self.patcher.stop()
        super().tearDown()

    def test_num_of_forms(self):
        users_by_id = {'user_id_1': self.web_user, 'user_id_2': self.mobile_user}
        with patch('corehq.apps.data_analytics.malt_generator.get_app_submission_breakdown_es') as mock_esquery:
            mock_esquery.return_value = [
                create_mock_nested_query_row(user_id='user_id_1', doc_count=50),
                create_mock_nested_query_row(user_id='user_id_2', doc_count=25),
            ]
            malt_row_dicts = _get_malt_row_dicts(self.domain, self.monthspan, users_by_id)

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
