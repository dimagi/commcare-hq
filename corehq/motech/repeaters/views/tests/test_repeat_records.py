from datetime import datetime

from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from unittest.mock import Mock

from corehq import privileges
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser
from corehq.form_processor.models import CommCareCase, XFormInstance
from corehq.form_processor.tests.utils import (
    create_case,
    create_form_for_test,
    sharded,
)
from corehq.motech.models import ConnectionSettings
from corehq.util.test_utils import privilege_enabled

from .. import repeaters
from .. import repeat_records
from ...models import CaseRepeater, FormRepeater, RepeatRecord, State


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

    def test__get_state(self):
        mock_request = Mock()
        state_values = [None, 'PENDING']
        expected_results = [None, State.Pending]
        for value, expected_result in zip(state_values, expected_results):
            mock_request.POST.get.return_value = value
            result = repeat_records._get_state(mock_request)
            assert result == expected_result

    def test__get_state_raises_key_error(self):
        mock_request = Mock()
        state_values = ['', 'ALL']
        for value in state_values:
            with self.assertRaises(KeyError):
                repeat_records._get_state(mock_request)


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

    def test_get_repeater_types_info(self):
        class view:
            domain = "test"
        state_counts = RepeatRecord.objects.count_by_repeater_and_state("test")
        infos = repeaters.DomainForwardingOptionsView.get_repeater_types_info(view, state_counts)
        repeater, = {i.class_name: i for i in infos}['FormRepeater'].instances

        self.assertEqual(repeater.count_State, {
            # templates that reference `count_State` may need to be
            # updated if the keys in this dict change
            'Cancelled': 0,
            'Empty': 0,
            'EmptyOrSuccess': 0,
            'ErrorGeneratingPayload': 0,
            'ErrorGeneratingPayloadOrRejected': 0,
            'Fail': 0,
            'PayloadRejected': 0,
            'Pending': 1,
            'Success': 0
        })


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


@sharded
class TestRepeatRecordPayloadPreview(TestCase):
    """HTTP tests for the ``RepeatRecordView`` GET (Payload preview) endpoint."""

    domain = "test-payload-preview"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(cls.domain)
        cls.addClassCleanup(cls.domain_obj.delete)
        cls.user = WebUser.create(
            cls.domain, "admin@example.com", "password",
            created_by=None, created_via=None,
        )
        cls.user.is_superuser = True
        cls.user.save()
        cls.addClassCleanup(cls.user.delete, cls.domain, deleted_by=None)
        conn = ConnectionSettings.objects.create(
            domain=cls.domain, name="test", url="https://test.com/",
        )
        cls.form_repeater = FormRepeater.objects.create(
            domain=cls.domain, connection_settings_id=conn.id,
            include_app_id_param=False,
        )
        cls.case_repeater = CaseRepeater.objects.create(
            domain=cls.domain, connection_settings_id=conn.id,
        )

    def setUp(self):
        super().setUp()
        self.client.login(username="admin@example.com", password="password")

    def _make_record(self, repeater, payload_id):
        return repeater.repeat_records.create(
            domain=self.domain,
            payload_id=payload_id,
            registered_at=datetime.utcnow(),
            next_check=datetime.utcnow(),
        )

    def _get_payload(self, record):
        return self.client.get(
            reverse(repeat_records.RepeatRecordView.urlname, kwargs={"domain": self.domain}),
            {"record_id": record.id},
        )

    @privilege_enabled(privileges.DATA_FORWARDING)
    def test_soft_deleted_form_payload_is_not_shown(self):
        form = create_form_for_test(self.domain, save=True)
        XFormInstance.objects.soft_delete_forms(self.domain, [form.form_id])
        record = self._make_record(self.form_repeater, form.form_id)

        response = self._get_payload(record)

        self.assertEqual(response.status_code, 404)

    @privilege_enabled(privileges.DATA_FORWARDING)
    def test_soft_deleted_case_payload_is_not_shown(self):
        case = create_case(self.domain, save=True)
        CommCareCase.objects.soft_delete_cases(self.domain, [case.case_id])
        record = self._make_record(self.case_repeater, case.case_id)

        response = self._get_payload(record)

        self.assertEqual(response.status_code, 404)

    @privilege_enabled(privileges.DATA_FORWARDING)
    def test_live_form_payload_is_shown(self):
        form = create_form_for_test(self.domain, save=True)
        record = self._make_record(self.form_repeater, form.form_id)

        response = self._get_payload(record)

        self.assertEqual(response.status_code, 200)
        self.assertIn('payload', response.json())
