from datetime import datetime

from django.test import SimpleTestCase, TestCase
from unittest.mock import Mock

from corehq.motech.models import ConnectionSettings

from .. import repeaters
from .. import repeat_records
from ...models import FormRepeater, RepeatRecord, State


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

    def test__get_states(self):
        mock_request = Mock()
        state_values = [None, '', 'PENDING', 'PAYLOADERROR']
        expected_results = [
            None,
            None,
            (State.Pending,),
            (State.PayloadRejected, State.ErrorGeneratingPayload),
        ]
        for value, expected_result in zip(state_values, expected_results):
            mock_request.POST.get.return_value = value
            result = repeat_records._get_states(mock_request)
            assert result == expected_result

    def test__get_states_raises_key_error(self):
        mock_request = Mock()
        mock_request.POST.get.return_value = 'ALL'
        with self.assertRaises(KeyError):
            repeat_records._get_states(mock_request)


class TestDomainForwardingOptionsView(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        conn = ConnectionSettings.objects.create(domain="test", name="test", url="https://test.com/")
        cls.repeater = FormRepeater.objects.create(
            domain="test",
            connection_settings_id=conn.id,
            include_app_id_param=False,
        )
        cls.record = cls.repeater.repeat_records.create(
            domain=cls.repeater.domain,
            payload_id="3978e5d2bc2346fe958b933870c5b28a",
            registered_at=datetime.utcnow(),
            next_check=datetime.utcnow(),
        )

    def _get_repeater_with_counts(self):
        class view:
            domain = "test"
        state_counts = RepeatRecord.objects.count_by_repeater_and_state("test")
        infos = repeaters.DomainForwardingOptionsView.get_repeater_types_info(view, state_counts)
        repeater, = {i.class_name: i for i in infos}['FormRepeater'].instances
        return repeater

    def test_get_repeater_types_info(self):
        repeater = self._get_repeater_with_counts()

        self.assertEqual(repeater.state_group_counts, {
            # templates that reference `state_group_counts` may need to
            # be updated if the keys in this dict change
            'SUCCESS': 0,
            'PENDING': 1,
            'CANCELLED': 0,
            'FAIL': 0,
            'PAYLOADERROR': 0,
        })

    def test_counts_include_every_state_in_a_group(self):
        for state in (
            State.Success,
            State.Empty,
            State.PayloadRejected,
            State.ErrorGeneratingPayload,
        ):
            self.repeater.repeat_records.create(
                domain=self.repeater.domain,
                payload_id="3978e5d2bc2346fe958b933870c5b28a",
                registered_at=datetime.utcnow(),
                state=state,
            )

        repeater = self._get_repeater_with_counts()

        assert repeater.state_group_counts['SUCCESS'] == 2
        assert repeater.state_group_counts['PAYLOADERROR'] == 2


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
