import mock
from django.test import TestCase

from celery.exceptions import TimeoutError
from celery.result import EagerResult, AsyncResult

from corehq.apps.domain.models import Domain
from casexml.apps.phone.restore import RestoreConfig, RestoreParams, AsyncRestoreResponse, FileRestoreResponse
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
        return RestoreConfig(
            project=self.project,
            restore_user=self.user,
            params=RestoreParams(sync_log_id=sync_log_id),
            async=async
        )

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
    def test_subsequent_restores_on_same_synclog_returns_async_restore_response(self, task):
        delay = mock.MagicMock()
        delay.id = 'random_task_id'
        delay.get = mock.MagicMock(side_effect=TimeoutError())  # task not finished
        task.delay.return_value = delay

        restore_config = self._restore_config(async=True)
        initial_payload = restore_config.get_payload()
        sync_log_id = restore_config.restore_state.current_sync_log._id
        self.assertTrue(isinstance(initial_payload, AsyncRestoreResponse))

        subsequent_restore = self._restore_config(async=True, sync_log_id=sync_log_id)
        subsequent_payload = subsequent_restore.get_payload()
        self.assertTrue(isinstance(subsequent_payload, AsyncRestoreResponse))

    def test_subsequent_restores_job_complete(self):
        # First sync, return a timout. Ensure that the async_task_id gets set
        with mock.patch.object(EagerResult, 'get', mock.MagicMock(side_effect=TimeoutError())):
            restore_config = self._restore_config(async=True)
            initial_payload = restore_config.get_payload()
            sync_log_id = restore_config.restore_state.current_sync_log._id
            self.assertIsNotNone(restore_config.restore_state.current_sync_log.async_task_id)
            self.assertTrue(isinstance(initial_payload, AsyncRestoreResponse))
            # new synclog should have been created
            self.assertIsNotNone(restore_config.restore_state.current_sync_log)

        # Second sync, don't timeout (can't use AsyncResult in tests, so mock
        # the return value). Ensure that the synclog is updated properly
        with mock.patch.object(AsyncResult, 'get', mock.MagicMock(return_value=FileRestoreResponse())):
            subsequent_restore = self._restore_config(async=True, sync_log_id=sync_log_id)
            self.assertIsNotNone(subsequent_restore.sync_log.async_task_id)
            subsequent_payload = subsequent_restore.get_payload()
            self.assertIsNone(subsequent_restore.sync_log.async_task_id)
            self.assertTrue(isinstance(subsequent_payload, FileRestoreResponse))
            # a new synclog should not have been created
            self.assertIsNone(subsequent_restore.restore_state.current_sync_log)

    # def submitting_form_for_synclog_kills_task_removes_async_id(self):
    #     """
    #     >>> from celery.task.control import revoke
    #     >>> revoke(task_id, terminate=True)
    #     """
    #     self.skipTest("")
