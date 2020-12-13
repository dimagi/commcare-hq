from django.http import QueryDict
from nose.tools import assert_equal

from corehq.motech.repeaters.views import repeat_records
from unittest.mock import Mock, patch
from unittest.case import TestCase

query_strings = [
    None,
    '',
    'repeater=&record_state=&payload_id=payload_3',
    'repeater=repeater_3&record_state=STATUS_2&payload_id=payload_2',
    'repeater=&record_state=&payload_id=',
    'repeater=repeater_1&record_state=STATUS_2&payload_id=payload_1',
    'repeater=&record_state=STATUS&payload_id=payload_2',
    'repeater=repeater_2&record_state=STATUS&payload_id=',
]


class TestUtilities(TestCase):

    def test__get_records(self):
        mock_request = Mock()
        mock_request.POST.get.side_effect = [
            None,
            '',
            'id_1 id_2 ',
            'id_1 id_2',
            ' id_1 id_2 ',
        ]
        expected_records_ids = [
            [],
            [],
            ['id_1', 'id_2'],
            ['id_1', 'id_2'],
            ['id_1', 'id_2'],
        ]

        for expected_result in expected_records_ids:
            records_ids = repeat_records._get_record_ids_from_request(mock_request)
            self.assertEqual(records_ids, expected_result)

    def test__get_flag(self):
        mock_request = Mock()
        flag_values = [None, '', 'flag']
        expected_results = ['', '', 'flag']
        for value, expected_result in zip(flag_values, expected_results):
            mock_request.POST.get.return_value = value
            result = repeat_records._get_flag(mock_request)
            assert_equal(result, expected_result)

    def test__change_record_state(self):
        strings_to_add = [
            'NO_STATUS',
            'NO_STATUS',
            None,
            '',
            'STATUS',
            'STATUS_2',
            'STATUS_3',
            'STATUS_4',
        ]
        desired_strings = [
            '',
            '',
            'repeater=&record_state=&payload_id=payload_3',
            'repeater=repeater_3&record_state=STATUS_2&payload_id=payload_2',
            'repeater=&record_state=STATUS&payload_id=',
            'repeater=repeater_1&record_state=STATUS_2&payload_id=payload_1',
            'repeater=&record_state=STATUS_3&payload_id=payload_2',
            'repeater=repeater_2&record_state=STATUS_4&payload_id=',
        ]

        for qs, str_to_add, expected_result in zip(query_strings,
                                                   strings_to_add,
                                                   desired_strings):
            result = repeat_records._change_record_state(qs, str_to_add)
            self.assertEqual(result, expected_result)

    @patch('corehq.motech.repeaters.views.repeat_records.task_generate_ids_and_operate_on_payloads')
    @patch('corehq.motech.repeaters.views.repeat_records.expose_cached_download')
    def test__schedule_task_with_flag_no_query(self,
                                               mock_expose_cache_download,
                                               mock_task_generate_ids_and_operate_on_payloads):
        mock_request = Mock()
        query_dict = QueryDict('a=1&b=2')
        mock_request.POST = query_dict
        mock_domain = 'domain_1'
        mock_action = 'action_1'

        repeat_records._schedule_task_with_flag(mock_request, mock_domain, mock_action)
        self._mock_schedule_task(query_dict, mock_domain, mock_action,
                                 mock_expose_cache_download,
                                 mock_task_generate_ids_and_operate_on_payloads)

    @patch('corehq.motech.repeaters.views.repeat_records.task_generate_ids_and_operate_on_payloads')
    @patch('corehq.motech.repeaters.views.repeat_records.expose_cached_download')
    def test__schedule_task_with_flag_with_query(self,
                                                 mock_expose_cache_download,
                                                 mock_task_generate_ids_and_operate_on_payloads):
        mock_request = Mock()
        query_dict = QueryDict('a=1&b=2')
        mock_request.POST = query_dict
        domain = 'domain_1'
        action = 'action_1'

        repeat_records._schedule_task_with_flag(mock_request, domain, action)
        self._mock_schedule_task(query_dict, domain, action,
                                 mock_expose_cache_download,
                                 mock_task_generate_ids_and_operate_on_payloads)

    @patch('corehq.motech.repeaters.views.repeat_records.task_operate_on_payloads')
    @patch('corehq.motech.repeaters.views.repeat_records.expose_cached_download')
    @patch('corehq.motech.repeaters.views.repeat_records._get_record_ids_from_request')
    def test__schedule_task_without_flag(self, mock__get_records, mock_expose_cache_download,
                                         mock_task_operate_on_payloads):
        mock_request = Mock()
        record_id_values = ['', None, 'a=1&b=2']
        mock_request.POST.get.side_effect = record_id_values
        domain = 'domain_1'
        action = 'action_1'

        for __ in record_id_values:
            repeat_records._schedule_task_without_flag(mock_request, domain, action)
            mock__get_records.assert_called_with(mock_request)
            mock_records_ids = mock__get_records(mock_request)
            self._mock_schedule_task(mock_records_ids, domain, action,
                                     mock_expose_cache_download, mock_task_operate_on_payloads)

    def _mock_schedule_task(self, data, domain, action, expose_cache_download, task_to_perform):
        expose_cache_download.assert_called_with(payload=None, expiry=1 * 60 * 60, file_extension=None)
        mock_task_ref = expose_cache_download(payload=None, expiry=1 * 60 * 60, file_extension=None)
        task_to_perform.delay.assert_called_with(data, domain, action)
        mock_task = task_to_perform.delay(data, domain, action)
        mock_task_ref.set_task.assert_called_with(mock_task)
