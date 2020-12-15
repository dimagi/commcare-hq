from django.http import QueryDict
from nose.tools import assert_equal

from corehq.motech.repeaters.views import repeat_records
from unittest.mock import Mock
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
