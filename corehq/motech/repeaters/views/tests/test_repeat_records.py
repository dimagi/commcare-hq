from datetime import datetime

from django.http import QueryDict
from django.test import SimpleTestCase, TestCase
from nose.tools import assert_equal
from unittest.mock import Mock

from corehq.motech.models import ConnectionSettings

from .. import repeat_records
from ...models import FormRepeater


class TestUtilities(SimpleTestCase):

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
            query_dict = QueryDict(qs)
            result = repeat_records._change_record_state(
                query_dict, str_to_add).urlencode()
            self.assertEqual(result, expected_result)


class TestRepeatRecordView(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        conn = ConnectionSettings.objects.create(domain="test", name="test", url="https://test.com/")
        cls.repeater = FormRepeater.objects.create(
            domain="test",
            connection_settings_id=conn.id,
            include_app_id_param=False,
        )

    def setUp(self):
        self.record = self.repeater.repeat_records.create(
            domain=self.repeater.domain,
            payload_id="3978e5d2bc2346fe958b933870c5b28a",
            registered_at=datetime.utcnow(),
            next_check=datetime.utcnow(),
        )

    def test_get_record_or_404(self):
        rec_id = str(self.record.id)
        record = repeat_records.RepeatRecordView.get_record_or_404("test", rec_id)
        self.assertEqual(record.id, int(rec_id))

    def test_get_record_or_404_with_int(self):
        rec_id = self.record.id
        record = repeat_records.RepeatRecordView.get_record_or_404("test", rec_id)
        self.assertEqual(record.id, rec_id)

    def test_get_record_or_404_not_found(self):
        rec_id = 40400000000000000000000000000404
        with self.assertRaises(repeat_records.Http404):
            repeat_records.RepeatRecordView.get_record_or_404("test", rec_id)

    def test_get_record_or_404_with_wrong_domain(self):
        rec_id = self.record.id
        with self.assertRaises(repeat_records.Http404):
            repeat_records.RepeatRecordView.get_record_or_404("wrong", rec_id)
