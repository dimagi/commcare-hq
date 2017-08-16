import mock
from cStringIO import StringIO
from django.test import TestCase, SimpleTestCase
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
    FileRestoreResponse,
    async_restore_task_id_cache_key,
    restore_payload_path_cache_key,
)
from casexml.apps.phone.tasks import get_async_restore_payload, ASYNC_RESTORE_SENT
from casexml.apps.phone.tests.utils import create_restore_user
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users
from corehq.util.test_utils import flag_enabled
from corehq.apps.receiverwrapper.util import submit_form_locally


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

    def _restore_config(self, async=True, sync_log_id='', overwrite_cache=False):
        restore_config = RestoreConfig(
            project=self.project,
            restore_user=self.user,
            params=RestoreParams(sync_log_id=sync_log_id, version=V2),
            cache_settings=RestoreCacheSettings(
                overwrite_cache=overwrite_cache
            ),
            async=async
        )
        self.addCleanup(restore_config.cache.clear)
        return restore_config


class AsyncRestoreTestCouchOnly(BaseAsyncRestoreTest):
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
        self.assertIsInstance(initial_payload, AsyncRestoreResponse)

        subsequent_restore = self._restore_config(async=True)
        subsequent_payload = subsequent_restore.get_payload()
        self.assertIsInstance(subsequent_payload, AsyncRestoreResponse)

    def test_subsequent_syncs_when_job_complete(self):
        # First sync, return a timout. Ensure that the async_task_id gets set
        cache_id = async_restore_task_id_cache_key(domain=self.domain, user_id=self.user.user_id)
        with mock.patch('casexml.apps.phone.restore.get_async_restore_payload') as task:
            delay = mock.MagicMock()
            delay.id = 'random_task_id'
            delay.get = mock.MagicMock(side_effect=TimeoutError())  # task not finished
            task.delay.return_value = delay

            restore_config = self._restore_config(async=True)
            initial_payload = restore_config.get_payload()
            self.assertIsNotNone(restore_config.cache.get(cache_id))
            self.assertIsInstance(initial_payload, AsyncRestoreResponse)
            # new synclog should not have been created
            self.assertIsNone(restore_config.restore_state.current_sync_log)

        # Second sync, don't timeout (can't use AsyncResult in tests, so mock
        # the return value).
        file_restore_response = mock.MagicMock(return_value=FileRestoreResponse())
        with mock.patch.object(AsyncResult, 'get', file_restore_response) as get_result:
            with mock.patch.object(AsyncResult, 'status', ASYNC_RESTORE_SENT):
                subsequent_restore = self._restore_config(async=True)
                self.assertIsNotNone(restore_config.cache.get(cache_id))
                subsequent_restore.get_payload()

                # if the task actually ran, the cache should now not have the task id,
                # however, the task is not run in this test. See `test_completed_task_deletes_cache`
                # self.assertIsNone(restore_config.cache.get(cache_id))

                get_result.assert_called_with(timeout=1)

    def test_completed_task_deletes_cache(self):
        cache_id = async_restore_task_id_cache_key(domain=self.domain, user_id=self.user.user_id)
        restore_config = self._restore_config(async=True)
        restore_config.cache.set(cache_id, 'im going to be deleted by the next command')
        restore_config.timing_context.start()
        restore_config.timing_context("wait_for_task_to_start").start()
        get_async_restore_payload.delay(restore_config)
        self.assertTrue(restore_config.timing_context.is_finished())
        self.assertIsNone(restore_config.cache.get(cache_id))

    def test_completed_task_creates_sync_log(self):
        restore_config = self._restore_config(async=True)
        restore_config.timing_context.start()
        restore_config.timing_context("wait_for_task_to_start").start()
        get_async_restore_payload.delay(restore_config)
        self.assertTrue(restore_config.timing_context.is_finished())
        self.assertIsNotNone(restore_config.restore_state.current_sync_log)

    def test_force_cache_on_async(self):
        restore_config = self._restore_config(async=True)
        self.assertTrue(restore_config.force_cache)

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

    @mock.patch.object(RestoreConfig, 'cache')
    @mock.patch.object(FileRestoreResponse, 'get_payload')
    @mock.patch('casexml.apps.phone.restore.get_async_restore_payload')
    def test_clears_cache(self, task, response, cache):
        delay = mock.MagicMock()
        delay.id = 'random_task_id'
        task.delay.return_value = delay
        response.return_value = StringIO('<restore_id>123</restore_id>')
        cache.get.return_value = 'path-to-cached-restore'

        self._restore_config(async=True, overwrite_cache=False).get_payload()
        self.assertFalse(cache.delete.called)

        self._restore_config(async=True, overwrite_cache=True).get_payload()
        self.assertTrue(cache.delete.called)


class AsyncRestoreTest(BaseAsyncRestoreTest):

    @flag_enabled('ASYNC_RESTORE')
    def test_restore_in_progress_form_submitted_kills_old_jobs(self):
        """If the user submits a form somehow while a job is running, the job should be terminated
        """
        task_cache_id = async_restore_task_id_cache_key(domain=self.domain, user_id=self.user.user_id)
        initial_sync_cache_id = restore_payload_path_cache_key(
            domain=self.domain,
            user_id=self.user.user_id,
            version='2.0'
        )
        fake_cached_thing = 'fake-cached-thing'
        restore_config = self._restore_config(async=True)
        # pretend we have a task running
        restore_config.cache.set(task_cache_id, fake_cached_thing)
        restore_config.cache.set(initial_sync_cache_id, fake_cached_thing)

        form = """
        <data xmlns="http://openrosa.org/formdesigner/blah">
            <meta>
                <userID>{user_id}</userID>
            </meta>
        </data>
        """

        with mock.patch('corehq.form_processor.submission_post.revoke_celery_task') as revoke:
            # with a different user in the same domain, task doesn't get killed
            submit_form_locally(form.format(user_id="other_user"), self.domain)
            self.assertFalse(revoke.called)
            self.assertEqual(restore_config.cache.get(task_cache_id), fake_cached_thing)
            self.assertEqual(restore_config.cache.get(initial_sync_cache_id), fake_cached_thing)

            # task gets killed when the user submits a form
            submit_form_locally(form.format(user_id=self.user.user_id), self.domain)
            revoke.assert_called_with(fake_cached_thing)
            self.assertIsNone(restore_config.cache.get(task_cache_id))
            self.assertIsNone(restore_config.cache.get(initial_sync_cache_id))

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

    @mock.patch.object(RestoreConfig, 'cache')
    @mock.patch.object(FileRestoreResponse, 'get_payload')
    @mock.patch('casexml.apps.phone.restore.get_async_restore_payload')
    def test_clears_cache(self, task, response, cache):
        delay = mock.MagicMock()
        delay.id = 'random_task_id'
        task.delay.return_value = delay
        cache.get.return_value = 'path-to-cached-restore'
        response.return_value = StringIO('<restore_id>123</restore_id>')

        self._restore_config(async=True, overwrite_cache=False).get_payload()
        self.assertFalse(cache.delete.called)

        self._restore_config(async=True, overwrite_cache=True).get_payload()
        self.assertTrue(cache.delete.called)


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
