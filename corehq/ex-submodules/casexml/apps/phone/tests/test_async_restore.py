from __future__ import absolute_import
from __future__ import unicode_literals
import mock
from io import BytesIO
from django.test import TestCase, SimpleTestCase, override_settings
from casexml.apps.phone.restore_caching import AsyncRestoreTaskIdCache, RestorePayloadPathCache
from corehq.apps.app_manager.tests.util import TestXmlMixin

from celery.exceptions import TimeoutError
from celery.result import AsyncResult

from casexml.apps.case.xml import V2
from casexml.apps.case.tests.util import (
    delete_all_cases,
    delete_all_sync_logs,
)
from corehq.apps.domain.models import Domain
from corehq.form_processor.tests.utils import use_sql_backend
from casexml.apps.phone.restore import (
    RestoreConfig,
    RestoreParams,
    RestoreCacheSettings,
    AsyncRestoreResponse,
    RestoreResponse,
)
from casexml.apps.phone.tasks import get_async_restore_payload, ASYNC_RESTORE_SENT
from casexml.apps.phone.tests.utils import create_restore_user
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users
from corehq.util.test_utils import flag_enabled
from corehq.apps.receiverwrapper.util import submit_form_locally
from dimagi.utils.couch.cache.cache_core import get_redis_default_cache


class BaseAsyncRestoreTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(BaseAsyncRestoreTest, cls).setUpClass()
        delete_all_cases()
        delete_all_sync_logs()
        delete_all_users()
        cls.domain = 'dummy-project'
        cls.project = Domain(name=cls.domain)
        cls.project.save()
        cls.user = create_restore_user(domain=cls.domain)

    @classmethod
    def tearDownClass(cls):
        cls.project.delete()
        delete_all_cases()
        delete_all_sync_logs()
        delete_all_users()
        super(BaseAsyncRestoreTest, cls).tearDownClass()

    def _restore_config(self, is_async=True, sync_log_id='', overwrite_cache=False):
        restore_config = RestoreConfig(
            project=self.project,
            restore_user=self.user,
            params=RestoreParams(sync_log_id=sync_log_id, version=V2),
            cache_settings=RestoreCacheSettings(
                overwrite_cache=overwrite_cache
            ),
            is_async=is_async
        )
        self.addCleanup(get_redis_default_cache().clear)
        return restore_config


class AsyncRestoreTestCouchOnly(BaseAsyncRestoreTest):
    @mock.patch('casexml.apps.phone.restore.get_async_restore_payload')
    def test_regular_restore_doesnt_start_task(self, task):
        """
        when the feature flag is off, the celery task does not get called
        """
        self._restore_config(is_async=False).get_payload()
        self.assertFalse(task.delay.called)

    @mock.patch('casexml.apps.phone.restore.get_async_restore_payload')
    def test_first_async_restore_kicks_off_task(self, task):
        delay = mock.MagicMock()
        delay.id = 'random_task_id'
        task.delay.return_value = delay

        self._restore_config(is_async=True).get_payload()
        self.assertTrue(task.delay.called)

    @mock.patch('casexml.apps.phone.restore.get_async_restore_payload')
    @override_settings(CELERY_TASK_ALWAYS_EAGER=False)
    def test_restore_then_sync_on_same_synclog_returns_async_restore_response(self, task):
        delay = mock.MagicMock()
        delay.id = 'random_task_id'
        delay.get = mock.MagicMock(side_effect=TimeoutError())  # task not finished
        task.delay.return_value = delay

        restore_config = self._restore_config(is_async=True)
        initial_payload = restore_config.get_payload()
        self.assertIsInstance(initial_payload, AsyncRestoreResponse)

        subsequent_restore = self._restore_config(is_async=True)
        subsequent_payload = subsequent_restore.get_payload()
        self.assertIsInstance(subsequent_payload, AsyncRestoreResponse)

    def test_subsequent_syncs_when_job_complete(self):
        # First sync, return a timout. Ensure that the async_task_id gets set
        async_restore_task_id_cache = AsyncRestoreTaskIdCache(
            domain=self.domain,
            user_id=self.user.user_id,
            sync_log_id=None,
            device_id=None,
        )
        with mock.patch('casexml.apps.phone.restore.get_async_restore_payload') as task:
            delay = mock.MagicMock()
            delay.id = 'random_task_id'
            delay.get = mock.MagicMock(side_effect=TimeoutError())  # task not finished
            task.delay.return_value = delay

            restore_config = self._restore_config(is_async=True)
            initial_payload = restore_config.get_payload()
            self.assertIsNotNone(async_restore_task_id_cache.get_value())
            self.assertIsInstance(initial_payload, AsyncRestoreResponse)
            # new synclog should not have been created
            self.assertIsNone(restore_config.restore_state.current_sync_log)

        # Second sync, don't timeout (can't use AsyncResult in tests, so mock
        # the return value).
        restore_response = mock.MagicMock(return_value=RestoreResponse(None))
        with mock.patch.object(AsyncResult, 'get', restore_response) as get_result:
            with mock.patch.object(AsyncResult, 'status', ASYNC_RESTORE_SENT):
                subsequent_restore = self._restore_config(is_async=True)
                self.assertIsNotNone(async_restore_task_id_cache.get_value())
                subsequent_restore.get_payload()

                # if the task actually ran, the cache should now not have the task id,
                # however, the task is not run in this test. See `test_completed_task_deletes_cache`
                # self.assertIsNone(restore_config.cache.get(cache_id))

                get_result.assert_called_with(timeout=1)

    def test_completed_task_deletes_cache(self):
        async_restore_task_id_cache = AsyncRestoreTaskIdCache(
            domain=self.domain,
            user_id=self.user.user_id,
            sync_log_id=None,
            device_id=None,
        )
        restore_config = self._restore_config(is_async=True)
        async_restore_task_id_cache.set_value('im going to be deleted by the next command')
        restore_config.timing_context.start()
        restore_config.timing_context("wait_for_task_to_start").start()
        get_async_restore_payload.delay(restore_config)
        self.assertTrue(restore_config.timing_context.is_finished())
        self.assertIsNone(async_restore_task_id_cache.get_value())

    def test_completed_task_creates_sync_log(self):
        restore_config = self._restore_config(is_async=True)
        restore_config.timing_context.start()
        restore_config.timing_context("wait_for_task_to_start").start()
        get_async_restore_payload.delay(restore_config)
        self.assertTrue(restore_config.timing_context.is_finished())
        self.assertIsNotNone(restore_config.restore_state.current_sync_log)

    @flag_enabled('ASYNC_RESTORE')
    def test_submit_form_no_userid(self):
        form = """
        <data xmlns="http://openrosa.org/formdesigner/blah">
            <meta>
                <deviceID>test</deviceID>
            </meta>
        </data>
        """
        submit_form_locally(form, self.domain)

    @mock.patch.object(RestorePayloadPathCache, 'invalidate')
    @mock.patch.object(RestorePayloadPathCache, 'exists')
    @mock.patch.object(RestoreResponse, 'as_file')
    @mock.patch('casexml.apps.phone.restore.get_async_restore_payload')
    @override_settings(CELERY_TASK_ALWAYS_EAGER=False)
    def test_clears_cache(self, task, response, exists_patch, invalidate):
        delay = mock.MagicMock()
        delay.id = 'random_task_id'
        task.delay.return_value = delay
        response.return_value = BytesIO(b'<restore_id>123</restore_id>')
        exists_patch.return_value = True

        self._restore_config(is_async=True, overwrite_cache=False).get_payload()
        self.assertFalse(invalidate.called)

        self._restore_config(is_async=True, overwrite_cache=True).get_payload()
        self.assertTrue(invalidate.called)


class AsyncRestoreTest(BaseAsyncRestoreTest):

    @flag_enabled('ASYNC_RESTORE')
    def test_restore_in_progress_form_submitted_kills_old_jobs(self):
        """If the user submits a form somehow while a job is running, the job should be terminated
        """
        last_sync_token = '0a72d5a3c2ec53e85c1af27ee5717e0d'
        device_id = 'RSMCHBA8PJNQIGMONN2JZT6E'
        async_restore_task_id_cache = AsyncRestoreTaskIdCache(
            domain=self.domain,
            user_id=self.user.user_id,
            sync_log_id=last_sync_token,
            device_id=device_id,
        )
        restore_payload_path_cache = RestorePayloadPathCache(
            domain=self.domain,
            user_id=self.user.user_id,
            device_id=device_id,
            sync_log_id=last_sync_token,
        )
        async_restore_task_id = '0edecc20d89d6f4a09f2e992c0c24b5f'
        initial_sync_path = 'path/to/payload'
        self._restore_config(is_async=True)
        # pretend we have a task running
        async_restore_task_id_cache.set_value(async_restore_task_id)
        restore_payload_path_cache.set_value(initial_sync_path)

        def submit_form(user_id, device_id, last_sync_token):
            form = """
            <data xmlns="http://openrosa.org/formdesigner/blah">
                <meta>
                    <userID>{user_id}</userID>
                    <deviceID>{device_id}</deviceID>
                </meta>
            </data>
            """
            submit_form_locally(
                form.format(user_id=user_id, device_id=device_id),
                self.domain,
                last_sync_token=last_sync_token,
            )

        with mock.patch('corehq.form_processor.submission_post.revoke_celery_task') as revoke:
            # with a different user in the same domain, task doesn't get killed
            submit_form(user_id="other_user", device_id='OTHERDEVICEID', last_sync_token='othersynctoken')
            self.assertFalse(revoke.called)
            self.assertEqual(async_restore_task_id_cache.get_value(), async_restore_task_id)
            self.assertEqual(restore_payload_path_cache.get_value(), initial_sync_path)

            # task gets killed when the user submits a form
            submit_form(user_id=self.user.user_id, device_id=device_id, last_sync_token=last_sync_token)
            revoke.assert_called_with(async_restore_task_id)
            self.assertIsNone(async_restore_task_id_cache.get_value())
            self.assertIsNone(restore_payload_path_cache.get_value())

    @flag_enabled('ASYNC_RESTORE')
    def test_submit_form_no_userid(self):
        form = """
        <data xmlns="http://openrosa.org/formdesigner/blah">
            <meta>
                <deviceID>test</deviceID>
            </meta>
        </data>
        """
        submit_form_locally(form, self.domain)

    @mock.patch.object(RestorePayloadPathCache, 'invalidate')
    @mock.patch.object(RestorePayloadPathCache, 'exists')
    @mock.patch.object(RestoreResponse, 'as_file')
    @mock.patch('casexml.apps.phone.restore.get_async_restore_payload')
    @override_settings(CELERY_TASK_ALWAYS_EAGER=False)
    def test_clears_cache(self, task, response, exists_patch, invalidate):
        delay = mock.MagicMock()
        delay.id = 'random_task_id'
        task.delay.return_value = delay
        exists_patch.return_value = True
        response.return_value = BytesIO(b'<restore_id>123</restore_id>')

        self._restore_config(is_async=True, overwrite_cache=False).get_payload()
        self.assertFalse(invalidate.called)

        self._restore_config(is_async=True, overwrite_cache=True).get_payload()
        self.assertTrue(invalidate.called)


@use_sql_backend
class AsyncRestoreTestSQL(AsyncRestoreTest):
    pass


class TestAsyncRestoreResponse(TestXmlMixin, SimpleTestCase):
    def setUp(self):
        self.task = mock.MagicMock()
        self.retry_after = 25
        self.task.info = {'done': 25, 'total': 100, 'retry-after': 25}
        self.username = 'mclovin'

        self.response = AsyncRestoreResponse(self.task, self.username)

    def test_response(self):
        expected = """
        <OpenRosaResponse xmlns="http://openrosa.org/http/response">
            <message nature='ota_restore_pending'>Asynchronous restore under way for {username}</message>
            <Sync xmlns="http://commcarehq.org/sync">
                <progress total="{total}" done="{done}" retry-after="{retry_after}"/>
            </Sync>
        </OpenRosaResponse>
        """.format(
            username=self.username,
            total=self.task.info['total'],
            done=self.task.info['done'],
            retry_after=self.retry_after,
        )
        self.assertXmlEqual(self.response.compile_response(), expected)

    def test_html_response(self):
        http_response = self.response.get_http_response()
        self.assertEqual(http_response.status_code, 202)
        self.assertTrue(http_response.has_header('Retry-After'))
        self.assertEqual(http_response['retry-after'], str(self.retry_after))
        self.assertXmlEqual(list(http_response.streaming_content)[0], self.response.compile_response())
