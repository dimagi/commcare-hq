from corehq.motech.repeaters.views import repeat_records
from unittest.mock import Mock, patch
from unittest.case import TestCase


class TestUtilities(TestCase):
    _BASE_STRINGS = [
        None,
        '',
        'repeater=&record_state=&payload_id=payload_3',
        'repeater=repeater_3&record_state=STATUS_2&payload_id=payload_2',
        'repeater=&record_state=&payload_id=',
        'repeater=repeater_1&record_state=STATUS_2&payload_id=payload_1',
        'repeater=&record_state=STATUS&payload_id=payload_2',
        'repeater=repeater_2&record_state=STATUS&payload_id=',
    ]

    def test__get_records(self):
        mock_request = Mock()
        mock_request.POST.get.side_effect = [None, '', 'id_1 id_2 ', 'id_1 id_2', ' id_1 id_2 ']
        expected_records_ids = [
            [],
            [],
            ['id_1', 'id_2'],
            ['id_1', 'id_2'],
            ['', 'id_1', 'id_2'],
        ]

        for r in range(5):
            records_ids = repeat_records._get_records(mock_request)
            self.assertEqual(records_ids, expected_records_ids[r])

    def test__get_query(self):
        mock_request = Mock()
        mock_request.POST.get.side_effect = [None, 'a=1&b=2']
        expected_queries = ['', 'a=1&b=2']

        for r in range(2):
            records_ids = repeat_records._get_query(mock_request)
            self.assertEqual(records_ids, expected_queries[r])

    def test__get_flag(self):
        mock_request = Mock()
        mock_request.POST.get.side_effect = [None, 'flag']
        expected_flags = ['', 'flag']

        for r in range(2):
            records_ids = repeat_records._get_flag(mock_request)
            self.assertEqual(records_ids, expected_flags[r])

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

        for r in range(8):
            returned_string = repeat_records._change_record_state(self._BASE_STRINGS[r], strings_to_add[r])
            self.assertEqual(returned_string, desired_strings[r])

    def test__url_parameters_to_dict(self):
        desired_dicts = [
            {},
            {},
            {'repeater': '', 'record_state': '', 'payload_id': 'payload_3'},
            {'repeater': 'repeater_3', 'record_state': 'STATUS_2', 'payload_id': 'payload_2'},
            {'repeater': '', 'record_state': '', 'payload_id': ''},
            {'repeater': 'repeater_1', 'record_state': 'STATUS_2', 'payload_id': 'payload_1'},
            {'repeater': '', 'record_state': 'STATUS', 'payload_id': 'payload_2'},
            {'repeater': 'repeater_2', 'record_state': 'STATUS', 'payload_id': ''},
        ]

        for r in range(8):
            returned_dict = repeat_records._url_parameters_to_dict(self._BASE_STRINGS[r])
            self.assertEqual(returned_dict, desired_dicts[r])

    @patch('corehq.motech.repeaters.views.repeat_records.task_generate_ids_and_operate_on_payloads')
    @patch('corehq.motech.repeaters.views.repeat_records.expose_cached_download')
    @patch('corehq.motech.repeaters.views.repeat_records._url_parameters_to_dict')
    @patch('corehq.motech.repeaters.views.repeat_records.six.moves.urllib.parse.unquote')
    @patch('corehq.motech.repeaters.views.repeat_records._get_query')
    def test__schedule_task_with_flag_no_query(self, mock__get_query, mock_unquote,
                                               mock__url_parameters_to_dict, mock_expose_cache_download,
                                               mock_task_generate_ids_and_operate_on_payloads):
        mock_request = Mock()
        mock_request.POST.get.return_value = ''
        mock__get_query.return_value = ''
        mock_domain = 'domain_1'
        mock_action = 'action_1'
        mock_data = {}

        repeat_records._schedule_task_with_flag(mock_request, mock_domain, mock_action)
        mock__get_query.assert_called_with(mock_request)
        mock_unquote.assert_not_called()
        mock__url_parameters_to_dict.assert_not_called()

        self._mock_schedule_task(mock_data, mock_domain, mock_action,
                                 mock_expose_cache_download, mock_task_generate_ids_and_operate_on_payloads)

    @patch('corehq.motech.repeaters.views.repeat_records.task_generate_ids_and_operate_on_payloads')
    @patch('corehq.motech.repeaters.views.repeat_records.expose_cached_download')
    @patch('corehq.motech.repeaters.views.repeat_records._url_parameters_to_dict')
    @patch('corehq.motech.repeaters.views.repeat_records.six.moves.urllib.parse.unquote')
    @patch('corehq.motech.repeaters.views.repeat_records._get_query')
    def test__schedule_task_with_flag_with_query(self, mock__get_query, mock_unquote,
                                                 mock__url_parameters_to_dict, mock_expose_cache_download,
                                                 mock_task_generate_ids_and_operate_on_payloads):
        mock_request = Mock()
        mock_request.POST.get.return_value = 'a=1&b=2'
        mock__get_query.return_value = 'a=1&b=2'
        domain = 'domain_1'
        action = 'action_1'

        repeat_records._schedule_task_with_flag(mock_request, domain, action)
        mock__get_query.assert_called_with(mock_request)
        mock_query = mock__get_query(mock_request)
        mock_unquote.assert_called_with(mock_query)
        mock_form_query_string = mock_unquote(mock_query)
        mock__url_parameters_to_dict.assert_called_with(mock_form_query_string)
        mock_data = mock__url_parameters_to_dict(mock_form_query_string)

        self._mock_schedule_task(mock_data, domain, action,
                                 mock_expose_cache_download, mock_task_generate_ids_and_operate_on_payloads)

    @patch('corehq.motech.repeaters.views.repeat_records.task_operate_on_payloads')
    @patch('corehq.motech.repeaters.views.repeat_records.expose_cached_download')
    @patch('corehq.motech.repeaters.views.repeat_records._url_parameters_to_dict')
    @patch('corehq.motech.repeaters.views.repeat_records.six.moves.urllib.parse.unquote')
    @patch('corehq.motech.repeaters.views.repeat_records._get_records')
    def test__schedule_task_without_flag(self, mock__get_records, mock_unquote,
                                         mock__url_parameters_to_dict, mock_expose_cache_download,
                                         mock_task_operate_on_payloads):
        mock_request = Mock()
        mock_request.POST.get.side_effect = ['', None, 'a=1&b=2']
        domain = 'domain_1'
        action = 'action_1'

        for r in range(3):
            repeat_records._schedule_task_without_flag(mock_request, domain, action)
            mock__get_records.assert_called_with(mock_request)
            mock_records_ids = mock__get_records(mock_request)
            mock_unquote.assert_not_called()
            mock__url_parameters_to_dict.assert_not_called()

            self._mock_schedule_task(mock_records_ids, domain, action,
                                     mock_expose_cache_download, mock_task_operate_on_payloads)

    def _mock_schedule_task(self, data, domain, action, expose_cache_download, task_to_perform):
        expose_cache_download.assert_called_with(payload=None, expiry=1 * 60 * 60, file_extension=None)
        mock_task_ref = expose_cache_download(payload=None, expiry=1 * 60 * 60, file_extension=None)
        task_to_perform.delay.asssert_called_with(data, domain, action)
        mock_task = task_to_perform.delay(data, domain, action)
        mock_task_ref.set_task.assert_called_with(mock_task)
