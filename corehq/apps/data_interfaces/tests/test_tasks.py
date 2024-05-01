from unittest.case import TestCase
from unittest.mock import patch

from corehq.apps.data_interfaces.tasks import (
    task_generate_ids_and_operate_on_payloads,
    task_operate_on_payloads,
    _get_repeat_record_ids,
)
from corehq.motech.repeaters.models import FormRepeater
from corehq.motech.repeaters.tests.test_models import RepeaterTestCase


class TestTasks(TestCase):

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
    @patch('corehq.apps.data_interfaces.tasks._get_repeat_record_ids')
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

    @patch('corehq.apps.data_interfaces.tasks._get_repeat_record_ids', lambda *a: [])
    def test_task_generate_ids_and_operate_on_payloads_no_data(self):
        response = task_generate_ids_and_operate_on_payloads(
            payload_id=None,
            repeater_id=None,
            domain='test_domain',
            action='',
        )
        self.assertEqual(response,
                         {'messages': {'errors': ['No payloads specified']}})


class TestRepeatRecordIdsQuery(RepeaterTestCase):

    def setUp(self):
        super().setUp()
        self.repeater2 = FormRepeater(
            domain="test",
            connection_settings=self.conn,
        )
        self.repeater2.save()

        self.record1 = self.new_record(payload_id='c0ffee')
        self.record2 = self.new_record(payload_id='deadbeef')
        self.record3 = self.new_record(payload_id='c0ffee', repeater=self.repeater2)

    def test_get_repeat_record_ids_by_payload_id(self):
        ids = _get_repeat_record_ids(
            repeater_id=None,
            payload_id="c0ffee",
            domain="test",
        )
        self.assertEqual(set(ids), {self.record1.id, self.record3.id})

    def test_get_repeat_record_ids_by_repeater_id(self):
        ids = _get_repeat_record_ids(
            repeater_id=self.repeater.id,
            payload_id=None,
            domain="test",
        )
        self.assertEqual(set(ids), {self.record1.id, self.record2.id})

    def test_get_repeat_record_ids_by_domain(self):
        ids = _get_repeat_record_ids(
            repeater_id=None,
            payload_id=None,
            domain="test",
        )
        self.assertEqual(set(ids), {self.record1.id, self.record2.id, self.record3.id})
