import mock
from django.test import TestCase, SimpleTestCase
from corehq.apps.app_manager.tests import TestXmlMixin

from celery.exceptions import TimeoutError
from celery.result import EagerResult, AsyncResult

from corehq.apps.domain.models import Domain
from casexml.apps.phone.restore import (
    RestoreConfig,
    RestoreParams,
    AsyncRestoreResponse,
    FileRestoreResponse,
    ASYNC_RETRY_AFTER
)
from casexml.apps.phone.tests.utils import create_restore_user
from casexml.apps.case.tests.util import (
    delete_all_cases,
    delete_all_sync_logs,
 )
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users


class AsyncRestoreTest(TestCase):
    dependent_apps = [
        'auditcare',
        'django_digest',
        'casexml.apps.phone',
        'casexml.apps.stock',
        'corehq.couchapps',
        'corehq.form_processor',
        'corehq.sql_accessors',
        'corehq.sql_proxy_accessors',
        'corehq.apps.domain',
        'corehq.apps.hqcase',
        'corehq.apps.products',
        'corehq.apps.reminders',
        'corehq.apps.sms',
        'corehq.apps.smsforms',
        'corehq.apps.notifications',
        'phonelog',
        'corehq.apps.domain',
    ]

    @classmethod
    def setUpClass(cls):
        super(AsyncRestoreTest, cls).setUpClass()
        delete_all_cases()
        delete_all_sync_logs()
        delete_all_users()
        cls.domain = 'dummy-project'
        cls.project = Domain(name=cls.domain)
        cls.project.save()
        cls.user = create_restore_user()

    @classmethod
    def tearDownClass(cls):
        cls.project.delete()
        delete_all_cases()
        delete_all_sync_logs()
        delete_all_users()
        super(AsyncRestoreTest, cls).tearDownClass()

    def _restore_config(self, async=True, sync_log_id=''):
        restore_config = RestoreConfig(
            project=self.project,
            restore_user=self.user,
            params=RestoreParams(sync_log_id=sync_log_id),
            async=async
        )
        self.addCleanup(restore_config.cache.clear)
        return restore_config

    @mock.patch('casexml.apps.phone.restore.get_async_restore_payload')
    def test_regular_restore_doesnt_start_task(self, task):
        """
        when the feature flag is off, the celery task does not get called
        """
        self._restore_config(async=False).get_payload()
        self.assertFalse(task.delay.called)

    @mock.patch('casexml.apps.phone.restore.get_async_restore_payload')
    def test_first_async_restore_kicks_off_task(self, task):
        delay = mock.MagicMock()
        delay.id = 'random_task_id'
        task.delay.return_value = delay

        self._restore_config(async=True).get_payload()
        self.assertTrue(task.delay.called)

    @mock.patch('casexml.apps.phone.restore.get_async_restore_payload')
    def test_restore_then_sync_on_same_synclog_returns_async_restore_response(self, task):
        delay = mock.MagicMock()
        delay.id = 'random_task_id'
        delay.get = mock.MagicMock(side_effect=TimeoutError())  # task not finished
        task.delay.return_value = delay

        restore_config = self._restore_config(async=True)
        initial_payload = restore_config.get_payload()
        self.assertTrue(isinstance(initial_payload, AsyncRestoreResponse))

        subsequent_restore = self._restore_config(async=True)
        subsequent_payload = subsequent_restore.get_payload()
        self.assertTrue(isinstance(subsequent_payload, AsyncRestoreResponse))

    def test_subsequent_syncs_when_job_complete(self):
        # First sync, return a timout. Ensure that the async_task_id gets set
        cache_id = "async-restore-{}".format(self.user.user_id)
        with mock.patch('casexml.apps.phone.restore.get_async_restore_payload') as task:
            delay = mock.MagicMock()
            delay.id = 'random_task_id'
            delay.get = mock.MagicMock(side_effect=TimeoutError())  # task not finished
            task.delay.return_value = delay

            restore_config = self._restore_config(async=True)
            initial_payload = restore_config.get_payload()
            self.assertIsNotNone(restore_config.cache.get(cache_id))
            self.assertTrue(isinstance(initial_payload, AsyncRestoreResponse))
            # new synclog should not have been created
            self.assertIsNone(restore_config.restore_state.current_sync_log)

        # Second sync, don't timeout (can't use AsyncResult in tests, so mock
        # the return value). Ensure that the synclog is updated properly
        with mock.patch.object(AsyncResult, 'get', mock.MagicMock(return_value=FileRestoreResponse())):
            subsequent_restore = self._restore_config(async=True)
            self.assertIsNotNone(restore_config.cache.get(cache_id))
            subsequent_payload = subsequent_restore.get_payload()
            self.assertIsNone(restore_config.cache.get(cache_id))
            self.assertTrue(isinstance(subsequent_payload, FileRestoreResponse))
            # a new synclog should not have been created
            self.assertIsNone(subsequent_restore.restore_state.current_sync_log)

    # def test_consecutive_restores_kills_old_jobs(self):
    #     """If the user does a fresh restore, jobs that are already queued or that have
    #     started should be killed

    #     """
    #     from casexml.apps.phone.models import (
    #         SyncLog,)
    #     with mock.patch.object(EagerResult, 'get', mock.MagicMock(side_effect=TimeoutError())):
    #         first_restore = self._restore_config(async=True)
    #         first_restore.get_payload()
    #         sync_log_id = first_restore.restore_state.current_sync_log._id
    #         self.assertIsNotNone(first_restore.restore_state.current_sync_log.async_task_id)

    #     second_restore = self._restore_config(async=True)
    #     second_restore.get_payload()
    #     self.assertIsNone(SyncLog.get(sync_log_id).async_task_id)

    # def submitting_form_for_synclog_kills_task_removes_async_id(self):
    #     """
    #     >>> from celery.task.control import revoke
    #     >>> revoke(task_id, terminate=True)
    #     """
    #     self.skipTest("")


class TestAsyncRestoreResponse(TestXmlMixin, SimpleTestCase):
    def setUp(self):
        self.task = mock.MagicMock()
        self.task.info = {'done': 25, 'total': 100}

        self.response = AsyncRestoreResponse(self.task)

    def test_response(self):
        expected = """
        <OpenRosaResponse xmlns="http://openrosa.org/http/response">
            <Sync xmlns="http://commcarehq.org/sync">
                <progress total="{total}" done="{done}" retry-after="{retry_after}"/>
            </Sync>
        </OpenRosaResponse>
        """.format(
            total=self.task.info['total'],
            done=self.task.info['done'],
            retry_after=ASYNC_RETRY_AFTER,
        )
        self.assertXmlEqual(self.response.compile_response(), expected)

    def test_html_response(self):
        http_response = self.response.get_http_response()
        self.assertEqual(http_response.status_code, 202)
        self.assertTrue(http_response.has_header('Retry-After'))
        self.assertEqual(http_response['retry-after'], str(ASYNC_RETRY_AFTER))
        self.assertXmlEqual(list(http_response.streaming_content)[0], self.response.compile_response())
