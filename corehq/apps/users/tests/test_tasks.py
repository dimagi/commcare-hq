import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from dateutil.relativedelta import relativedelta
from unittest.mock import patch, Mock

from django.contrib.auth.models import User
from django.test import TestCase

from couchdbkit import ResourceConflict

from corehq.apps.app_manager.models import Application, CredentialApplication
from corehq.apps.data_analytics.models import MALTRow
from corehq.apps.data_analytics.tests.test_malt_generator import create_malt_row_dict
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.enterprise.tests.utils import create_enterprise_permissions
from corehq.apps.es import case_search_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.apps.hqcase.case_helper import CaseCopier
from corehq.apps.reports.util import domain_copied_cases_by_owner
from corehq.apps.users.credentials_issuing import get_credentials_to_submit
from corehq.apps.users.dbaccessors import delete_all_users
from corehq.apps.users.models import (
    ActivityLevel,
    CommCareUser,
    ConnectIDUserLink,
    UserCredential,
    UserReportingMetadataStaging,
    WebUser,
)
from corehq.apps.users.tasks import (
    _process_reporting_metadata_staging,
    apply_correct_demo_mode_to_loadtest_user,
    process_mobile_worker_credentials,
    remove_users_test_cases,
    update_domain_date,
)
from corehq.form_processor.models import CommCareCase
from corehq.util.test_utils import new_db_connection


class TasksTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        delete_all_users()

        # Set up domains
        cls.domain = create_domain('test')
        cls.addClassCleanup(cls.domain.delete)
        cls.mirror_domain = create_domain('mirror')
        cls.addClassCleanup(cls.mirror_domain.delete)
        create_enterprise_permissions('web@web.com', 'test', ['mirror'])

        # Set up user
        cls.web_user = WebUser.create(
            domain='test',
            username='web',
            password='secret',
            created_by=None,
            created_via=None,
        )
        cls.addClassCleanup(cls.web_user.delete, None, None)

        cls.today = datetime.today().date()
        cls.last_week = cls.today - timedelta(days=7)

    def _last_accessed(self, user, domain):
        domain_membership = user.get_domain_membership(domain, allow_enterprise=False)
        if domain_membership:
            return domain_membership.last_accessed
        return None

    def test_update_domain_date_web_user(self):
        self.assertIsNone(self._last_accessed(self.web_user, self.domain.name))
        update_domain_date(self.web_user.user_id, self.domain.name)
        self.web_user = WebUser.get_by_username(self.web_user.username)
        self.assertEqual(self._last_accessed(self.web_user, self.domain.name), self.today)

    def test_update_domain_date_web_user_mirror(self):
        # Mirror domain access shouldn't be updated because user doesn't have a real membership
        self.assertIsNone(self._last_accessed(self.web_user, self.mirror_domain.name))
        update_domain_date(self.web_user.user_id, self.mirror_domain.name)
        self.web_user = WebUser.get_by_username(self.web_user.username)
        self.assertIsNone(self._last_accessed(self.web_user, self.mirror_domain.name))


@patch('corehq.apps.users.models.CouchUser.get_user_session_data', new=lambda _, __: {})
class TestLoadtestUserIsDemoUser(TestCase):

    def test_set_loadtest_factor_on_demo_user(self):
        with _get_user(loadtest_factor=5, is_demo_user=True) as user:
            apply_correct_demo_mode_to_loadtest_user(user.user_id)

            user = CommCareUser.get_by_user_id(user.user_id)
            self.assertTrue(user.is_demo_user)
            self.assertFalse(user.is_loadtest_user)

    def test_set_loadtest_factor_on_non_demo_user(self):
        with _get_user(loadtest_factor=5, is_demo_user=False) as user:
            apply_correct_demo_mode_to_loadtest_user(user.user_id)

            user = CommCareUser.get_by_user_id(user.user_id)
            self.assertTrue(user.is_demo_user)
            self.assertTrue(user.is_loadtest_user)

    def test_unset_loadtest_factor_on_demo_user(self):
        with _get_user(loadtest_factor=None, is_demo_user=True) as user:
            self.assertFalse(user.is_loadtest_user)
            apply_correct_demo_mode_to_loadtest_user(user.user_id)

            user = CommCareUser.get_by_user_id(user.user_id)
            self.assertTrue(user.is_demo_user)
            self.assertFalse(user.is_loadtest_user)

    def test_unset_loadtest_factor_on_non_demo_user(self):
        with _get_user(loadtest_factor=None, is_demo_user=False) as user:
            user.is_loadtest_user = True
            apply_correct_demo_mode_to_loadtest_user(user.user_id)

            user = CommCareUser.get_by_user_id(user.user_id)
            self.assertFalse(user.is_demo_user)
            self.assertFalse(user.is_loadtest_user)


@contextmanager
def _get_user(loadtest_factor, is_demo_user):
    domain_name = 'test-domain'
    domain_obj = create_domain(domain_name)
    just_now = datetime.utcnow().isoformat(timespec='seconds') + 'Z'
    user = CommCareUser.wrap({
        'domain': domain_name,
        'username': f'testy@{domain_name}.commcarehq.org',
        'loadtest_factor': loadtest_factor,
        'is_demo_user': is_demo_user,
        'date_joined': just_now,
    })
    user.save()
    try:
        yield user

    finally:
        user.delete(domain_name, None)
        domain_obj.delete()


@es_test(requires=[case_search_adapter])
class TestRemoveUsersTestCases(TestCase):

    domain = "test-domain"

    @classmethod
    def setUpClass(cls):
        super()
        cls.user = CommCareUser.create(cls.domain, 'user', 'password', None, None)

    @classmethod
    def tearDownClass(cls):
        cls.user.delete(deleted_by_domain=None, deleted_by=None)
        super()

    def test_only_copied_cases_gets_removed(self):
        _ = self._send_case_to_es(owner_id=self.user.user_id)
        test_case = self._send_case_to_es(owner_id=self.user.user_id, is_copy=True)

        remove_users_test_cases(self.domain, [self.user.user_id])
        case_ids = domain_copied_cases_by_owner(self.domain, self.user.user_id)

        self.assertEqual(case_ids, [test_case.case_id])

    def _send_case_to_es(
        self,
        owner_id=None,
        is_copy=False,
    ):
        case_json = {}
        if is_copy:
            case_json[CaseCopier.COMMCARE_CASE_COPY_PROPERTY_NAME] = 'case_id'

        case = CommCareCase(
            case_id=uuid.uuid4().hex,
            domain=self.domain,
            owner_id=owner_id,
            type='case_type',
            case_json=case_json,
            modified_on=datetime.utcnow(),
            server_modified_on=datetime.utcnow(),
        )
        case.save()

        case_search_adapter.index(case, refresh=True)
        return case


@patch.object(UserReportingMetadataStaging, 'process_record')
class TestProcessReportingMetadataStaging(TestCase):

    def test_record_is_deleted_if_processed_successfully(self, mock_process_record):
        record = UserReportingMetadataStaging.objects.create(user_id=self.user._id, domain='test-domain')
        self.assertTrue(UserReportingMetadataStaging.objects.get(id=record.id))

        _process_reporting_metadata_staging()

        self.assertEqual(mock_process_record.call_count, 1)
        self.assertEqual(UserReportingMetadataStaging.objects.all().count(), 0)

    def test_record_is_not_deleted_if_not_processed_successfully(self, mock_process_record):
        record = UserReportingMetadataStaging.objects.create(user_id=self.user._id, domain='test-domain')
        mock_process_record.side_effect = Exception

        with self.assertRaises(Exception):
            _process_reporting_metadata_staging()

        self.assertEqual(mock_process_record.call_count, 1)
        self.assertTrue(UserReportingMetadataStaging.objects.get(id=record.id))

    def test_process_record_is_retried_successfully_after_resource_conflict_raised(self, mock_process_record):
        # Simulate the scenario where the first attempt to process a record raises ResourceConflict
        # but the next attempt succeeds
        mock_process_record.side_effect = [ResourceConflict, None]
        UserReportingMetadataStaging.objects.create(user_id=self.user._id, domain='test-domain')

        _process_reporting_metadata_staging()

        self.assertEqual(mock_process_record.call_count, 2)
        self.assertEqual(UserReportingMetadataStaging.objects.all().count(), 0)

    def test_process_record_raises_resource_conflict_after_three_tries(self, mock_process_record):
        # ResourceConflict will always be raised when calling mock_process_record
        mock_process_record.side_effect = ResourceConflict
        UserReportingMetadataStaging.objects.create(user_id=self.user._id, domain='test-domain')

        with self.assertRaises(ResourceConflict):
            _process_reporting_metadata_staging()

        self.assertEqual(mock_process_record.call_count, 3)
        self.assertEqual(UserReportingMetadataStaging.objects.all().count(), 1)

    def test_subsequent_records_are_not_processed_if_exception_raised(self, mock_process_record):
        mock_process_record.side_effect = [Exception, None]
        UserReportingMetadataStaging.objects.create(user_id=self.user._id, domain='test-domain')
        UserReportingMetadataStaging.objects.create(user_id=self.user._id, domain='test-domain')

        with self.assertRaises(Exception):
            _process_reporting_metadata_staging()

        self.assertEqual(mock_process_record.call_count, 1)
        self.assertEqual(UserReportingMetadataStaging.objects.all().count(), 2)

    def setUp(self):
        super().setUp()
        self.user = CommCareUser.create('test-domain', 'test-username', 'qwer1234', None, None)
        self.addCleanup(self.user.delete, 'test-domain', deleted_by=None)


@patch.object(UserReportingMetadataStaging, 'process_record')
class TestProcessReportingMetadataStagingTransaction(TestCase):
    """
    This is testing the same method as TestProcessReportingMetadataStaging is above, but
    this is specifically testing how the method behaves when a record is locked.
    In order to reproduce this scenario without using a TransactionTestCase, which has a
    heavy handed cleanup process that can disrupt other tests, we need to create the initial
    records outside of the TestCase transaction, otherwise the records will not be available
    from another db connection. No other test should be added to this class as ``select_for_update``
    will hold a lock for the duration of the outer transaction, and the general cleanup/teardown
    here is kludgy.
    """
    def test_subsequent_records_are_processed_if_record_is_locked(self, mock_process_record):
        _ = UserReportingMetadataStaging.objects.select_for_update().get(pk=self.record.id)
        with new_db_connection():
            _process_reporting_metadata_staging()

        self.assertEqual(mock_process_record.call_count, 1)
        self.assertEqual(UserReportingMetadataStaging.objects.all().count(), 1)

    @classmethod
    def setUpClass(cls):
        cls.user = CommCareUser.create('test-domain', 'test-username', 'qwer1234', None, None)
        # Create the records outside of the TestCase transaction to ensure they are committed/saved
        # to the db by the time the method under tests attempts to read from the database
        # Because this is outside of a transaction, we are responsible for cleaning these up
        cls.record = UserReportingMetadataStaging.objects.create(user_id=cls.user._id, domain='test-domain')
        cls.record_two = UserReportingMetadataStaging.objects.create(user_id=cls.user._id, domain='test-domain')
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        # Cleanup needs to be done outside of the TestCase transaction to ensure it is not rolled back
        # Notably, the user is currently stored in couch and could be done within the transaction, but
        # for consistency it is here
        cls.user.delete('test-domain', deleted_by=None)
        cls.record.delete()
        cls.record_two.delete()


@patch('corehq.apps.users.credentials_issuing.requests.models.Response.raise_for_status')
@patch('corehq.apps.users.credentials_issuing.requests.post')
class TestProcessMobileWorkerCredentials(TestCase):
    domain = 'test-domain'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.one_month_app = Application.new_app(
            domain=cls.domain,
            name="One Month Test App",
        )
        cls.one_month_app._id = uuid.uuid4().hex
        cls.one_month_app.save()

        cls.three_month_app = Application.new_app(
            domain=cls.domain,
            name="Three Month Test App",
        )
        cls.three_month_app._id = uuid.uuid4().hex
        cls.three_month_app.save()

        cls.user1 = User.objects.create(username='user1', password='password')
        cls.user2 = User.objects.create(username='user2', password='password')
        cls.user3 = User.objects.create(username='user3', password='password')

        ConnectIDUserLink.objects.create(
            connectid_username=cls.user1.username,
            commcare_user=cls.user1,
            domain=cls.domain,
        )
        ConnectIDUserLink.objects.create(
            connectid_username=cls.user2.username,
            commcare_user=cls.user2,
            domain=cls.domain,
        )

        CredentialApplication.objects.create(
            domain=cls.domain,
            app_id=cls.one_month_app.id,
            activity_level=ActivityLevel.ONE_MONTH,
        )
        CredentialApplication.objects.create(
            domain=cls.domain,
            app_id=cls.three_month_app.id,
            activity_level=ActivityLevel.THREE_MONTHS,
        )

    @classmethod
    def tearDownClass(cls):
        delete_all_users()
        cls.one_month_app.delete()
        cls.three_month_app.delete()
        ConnectIDUserLink.objects.all().delete()
        CredentialApplication.objects.all().delete()
        UserCredential.objects.all().delete()
        super().tearDownClass()

    def _create_malt_rows(self, months, user, app, offset=0):
        for i in range(months):
            malt_row_dict = create_malt_row_dict({
                'month': datetime.now(timezone.utc) - relativedelta(months=i + offset + 1),
                'num_of_forms': 1,
                'user_type': 'CommCareUser',
                'user_id': user.id,
                'app_id': app.id,
                'username': user.username,
            })
            MALTRow.objects.create(**malt_row_dict)

    def test_process_credentials(self, mock_post, mock_status_raise):
        mock_response = Mock()
        mock_response.json.return_value = {'success': [0]}
        mock_post.return_value = mock_response

        self._create_malt_rows(3, self.user1, self.three_month_app)
        process_mobile_worker_credentials()
        cred = UserCredential.objects.get(user_id=self.user1.id, app_id=self.three_month_app.id)
        assert cred.issued_on is not None

    def test_process_multiple_credentials(self, mock_post, mock_status_raise):
        self._create_malt_rows(3, self.user1, self.one_month_app)
        self._create_malt_rows(3, self.user2, self.three_month_app)
        process_mobile_worker_credentials()
        assert UserCredential.objects.all().count() == 2

    def test_no_credentials(self, mock_post, mock_status_raise):
        self._create_malt_rows(1, self.user3, self.three_month_app)
        process_mobile_worker_credentials()
        assert UserCredential.objects.all().count() == 0

    def test_no_consecutive_activity(self, mock_post, mock_status_raise):
        self._create_malt_rows(1, self.user1, self.three_month_app)
        self._create_malt_rows(2, self.user1, self.three_month_app, offset=2)
        process_mobile_worker_credentials()
        assert UserCredential.objects.all().count() == 0

    def test_credentials_already_exist(self, mock_post, mock_status_raise):
        UserCredential.objects.create(
            user_id=self.user1.id,
            app_id=self.one_month_app.id,
        )
        self._create_malt_rows(1, self.user1, self.one_month_app)
        process_mobile_worker_credentials()
        assert UserCredential.objects.all().count() == 1

    @patch('corehq.apps.users.credentials_issuing.MAX_USERNAMES_PER_CREDENTIAL', new=1)
    def test_get_credentials_to_submit(self, mock_post, mock_status_raise):
        cred1 = UserCredential.objects.create(
            domain=self.domain,
            user_id=self.user1.id,
            username=self.user1.username,
            app_id=self.one_month_app.id,
            activity_level=ActivityLevel.ONE_MONTH
        )
        cred2 = UserCredential.objects.create(
            domain=self.domain,
            user_id=self.user2.id,
            username=self.user2.username,
            app_id=self.one_month_app.id,
            activity_level=ActivityLevel.ONE_MONTH
        )
        credentials_to_submit, credential_id_groups_to_update = get_credentials_to_submit()
        assert credentials_to_submit == [
            {
                'usernames': [self.user1.username],
                'title': 'One Month Test App',
                'type': 'APP_ACTIVITY',
                'level': '1MON_ACTIVE',
                'slug': self.one_month_app.id,
                'app_id': self.one_month_app.id,
            },
            {
                'usernames': [self.user2.username],
                'title': 'One Month Test App',
                'type': 'APP_ACTIVITY',
                'level': '1MON_ACTIVE',
                'slug': self.one_month_app.id,
                'app_id': self.one_month_app.id,
            }
        ]
        assert credential_id_groups_to_update == [
            [cred1.id], [cred2.id]
        ]
