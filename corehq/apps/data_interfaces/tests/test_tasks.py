from unittest.case import TestCase
from unittest.mock import patch

from corehq.apps.data_interfaces.tasks import (
    task_generate_ids_and_operate_on_payloads,
    task_operate_on_payloads,
)


class TestTasks(TestCase):

    def test_task_operate_on_payloads_no_action(self):
        response = task_operate_on_payloads(
            record_ids=['payload_id'],
            domain='test_domain',
            action=''
        )
        self.assertEqual(response,
                         {'messages': {'errors': ['No action specified']}})

    def test_task_operate_on_payloads_no_payload_ids(self):
        response = task_operate_on_payloads(
            record_ids=[],
            domain='test_domain',
            action='test_action'
        )
        self.assertEqual(response,
                         {'messages': {'errors': ['No payloads specified']}})

    @patch('corehq.apps.data_interfaces.tasks._get_repeat_record_ids')
    def test_task_generate_ids_and_operate_on_payloads_no_action(
        self,
        get_repeat_record_ids_mock,
    ):
        get_repeat_record_ids_mock.return_value = ['c0ffee', 'deadbeef']
        response = task_generate_ids_and_operate_on_payloads(
            query_string_dict={'payload_id': 'c0ffee'},
            domain='test_domain',
            action=''
        )
        self.assertEqual(response,
                         {'messages': {'errors': ['No action specified']}})

    def test_task_generate_ids_and_operate_on_payloads_no_data(self):
        response = task_generate_ids_and_operate_on_payloads(
            query_string_dict={},
            domain='test_domain',
            action=''
        )
        self.assertEqual(response,
                         {'messages': {'errors': ['No payloads specified']}})
