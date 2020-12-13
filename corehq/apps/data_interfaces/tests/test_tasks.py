from unittest.mock import patch, Mock
from unittest.case import TestCase

from corehq.apps.data_interfaces.tasks import task_operate_on_payloads, task_generate_ids_and_operate_on_payloads


class TestTasks(TestCase):

    @patch('corehq.apps.data_interfaces.tasks.operate_on_payloads')
    def test_task_operate_on_payloads_no_action(self, mock_operate_on_payloads):
        response = task_operate_on_payloads(
            record_ids=['payload_id'],
            domain='test_domain',
            action=''
        )
        self.assertEqual(response,
                         {'messages': {'errors': ['No action specified']}})
        self.assertEqual(mock_operate_on_payloads.call_count, 0)

    @patch('corehq.apps.data_interfaces.tasks.operate_on_payloads')
    def test_task_operate_on_payloads_no_payload_ids(self, mock_operate_on_payloads):
        response = task_operate_on_payloads(
            record_ids=[],
            domain='test_domain',
            action='test_action'
        )
        self.assertEqual(response,
                         {'messages': {'errors': ['No Payloads are supplied']}})
        self.assertEqual(mock_operate_on_payloads.call_count, 0)

    @patch('corehq.apps.data_interfaces.tasks.operate_on_payloads')
    @patch('corehq.apps.data_interfaces.tasks.task_operate_on_payloads')
    def test_task_operate_on_payloads_valid(self, mock_task, mock_operate_on_payloads):
        task_operate_on_payloads(
            record_ids=['payload_id'],
            domain='test_domain',
            action='test_action',
        )

        self.assertEqual(mock_operate_on_payloads.call_count, 1)
        mock_operate_on_payloads.assert_called_with(['payload_id'], 'test_domain', 'test_action', mock_task)

    @patch('corehq.apps.data_interfaces.tasks.generate_ids_and_operate_on_payloads')
    def test_task_generate_ids_and_operate_on_payloads_no_action(self, mock_generate_ids):
        with patch('corehq.apps.data_interfaces.tasks._') as _:
            response = task_generate_ids_and_operate_on_payloads(
                query_string_dict=['payload_id'],
                domain='test_domain',
                action=''
            )
            expected_response = {'messages': {'errors': [_('No action specified')]}}

        self.assertEqual(response, expected_response)
        self.assertEqual(mock_generate_ids.call_count, 0)

    @patch('corehq.apps.data_interfaces.tasks.generate_ids_and_operate_on_payloads')
    def test_task_generate_ids_and_operate_on_payloads_no_data(self, mock_generate_ids):
        with patch('corehq.apps.data_interfaces.tasks._') as _:
            response = task_generate_ids_and_operate_on_payloads(
                query_string_dict=[],
                domain='test_domain',
                action=''
            )
            expected_response = {'messages': {'errors': [_('No data is supplied')]}}

        self.assertEqual(response, expected_response)
        self.assertEqual(mock_generate_ids.call_count, 0)

    @patch('corehq.apps.data_interfaces.tasks.generate_ids_and_operate_on_payloads')
    @patch('corehq.apps.data_interfaces.tasks.task_generate_ids_and_operate_on_payloads')
    def test_task_generate_ids_and_operate_on_payloads_valid(self, mock_task, mock_generate_ids):
        task_generate_ids_and_operate_on_payloads(
            query_string_dict=['payload_id'],
            domain='test_domain',
            action='test_action',
        )

        self.assertEqual(mock_generate_ids.call_count, 1)
        mock_generate_ids.assert_called_with(['payload_id'], 'test_domain', 'test_action', mock_task)
