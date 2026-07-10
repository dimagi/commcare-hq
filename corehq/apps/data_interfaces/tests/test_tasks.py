from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from corehq.apps.data_interfaces.models import BulkAsyncJob
from corehq.apps.data_interfaces.tasks import (
    bulk_form_action_async,
    task_generate_ids_and_operate_on_payloads,
    task_operate_on_payloads,
)
from corehq.form_processor.models.forms import XFormInstance

TASK_DOMAIN = 'bulk-task-test'


class TestTasks(SimpleTestCase):

    @patch('corehq.apps.data_interfaces.utils.DownloadBase')
    @patch('corehq.apps.data_interfaces.utils._get_sql_repeat_record')
    def test_task_operate_on_payloads_no_action(
        self,
        unused_1,
        unused_2,
    ):
        response = task_operate_on_payloads(
            record_ids=['payload_id'],
            domain='test_domain',
            action='',
        )
        self.assertEqual(response, {
            'messages': {
                'errors': [
                    "Could not perform action for repeat record (id=payload_id): "
                    "Unknown action ''",
                ],
                'success': [],
                'success_count_msg': '',
            }
        })

    def test_task_operate_on_payloads_no_payload_ids(self):
        response = task_operate_on_payloads(
            record_ids=[],
            domain='test_domain',
            action='test_action',
        )
        self.assertEqual(response,
                         {'messages': {'errors': ['No payloads specified']}})

    @patch('corehq.apps.data_interfaces.utils.DownloadBase')
    @patch('corehq.apps.data_interfaces.utils._get_sql_repeat_record')
    @patch('corehq.apps.data_interfaces.tasks.RepeatRecord.objects.get_repeat_record_ids')
    def test_task_generate_ids_and_operate_on_payloads_no_action(
        self,
        get_repeat_record_ids_mock,
        unused_1,
        unused_2,
    ):

        get_repeat_record_ids_mock.return_value = ['c0ffee', 'deadbeef']
        response = task_generate_ids_and_operate_on_payloads(
            payload_id='c0ffee',
            repeater_id=None,
            domain='test_domain',
            action='',
        )
        self.assertEqual(response, {
            'messages': {
                'errors': [
                    "Could not perform action for repeat record (id=c0ffee): "
                    "Unknown action ''",
                    "Could not perform action for repeat record (id=deadbeef): "
                    "Unknown action ''",
                ],
                'success': [],
                'success_count_msg': '',
            }
        })

    @patch('corehq.apps.data_interfaces.tasks.RepeatRecord.objects.get_repeat_record_ids')
    def test_task_generate_ids_and_operate_on_payloads_no_data(self, get_repeat_record_ids_mock):
        get_repeat_record_ids_mock.return_value = []
        response = task_generate_ids_and_operate_on_payloads(
            payload_id=None,
            repeater_id=None,
            domain='test_domain',
            action='',
        )
        self.assertEqual(response,
                         {'messages': {'errors': ['No payloads specified']}})


class TestBulkFormActionAsync(TestCase):

    def _job(self):
        job = BulkAsyncJob(
            domain=TASK_DOMAIN, model=XFormInstance,
            action=BulkAsyncJob.Action.ARCHIVE, requested_by='u',
        )
        job.save()
        return job

    def test_task_runs_job(self):
        job = self._job()
        with patch(
            'corehq.apps.data_interfaces.tasks.run_bulk_form_action'
        ) as mock_run:
            bulk_form_action_async(str(job.id), TASK_DOMAIN)
        assert mock_run.call_count == 1
        assert mock_run.call_args[0][0].id == job.id

    def test_task_marks_job_failed_on_error(self):
        job = self._job()
        with patch(
            'corehq.apps.data_interfaces.tasks.run_bulk_form_action',
            side_effect=ValueError('boom'),
        ), self.assertRaises(ValueError):
            bulk_form_action_async(str(job.id), TASK_DOMAIN)
        job.refresh_from_db()
        assert job.status == BulkAsyncJob.Status.FAILED
