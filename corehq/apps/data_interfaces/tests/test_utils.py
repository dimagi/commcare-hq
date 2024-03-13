from datetime import datetime
from unittest.mock import Mock, patch
from uuid import uuid4

from django.test import SimpleTestCase, TestCase

from couchdbkit import ResourceNotFound

from corehq.apps.data_interfaces.tasks import (
    _get_repeat_record_ids,
    task_generate_ids_and_operate_on_payloads,
)
from corehq.apps.data_interfaces.utils import (
    _get_couch_repeat_record,
    operate_on_payloads,
)
from corehq.motech.models import ConnectionSettings
from corehq.motech.repeaters.models import (
    FormRepeater,
    RepeatRecord,
    SQLRepeatRecord,
)

DOMAIN = 'test-domain'


class TestUtils(SimpleTestCase):

    def test__get_ids_no_data(self):
        response = _get_repeat_record_ids(None, None, 'test_domain', False)
        self.assertEqual(response, [])

    @patch('corehq.apps.data_interfaces.tasks.get_couch_repeat_record_ids_by_payload_id')
    @patch('corehq.apps.data_interfaces.tasks.iter_repeat_record_ids_by_repeater')
    def test__get_ids_payload_id_in_data(
        self,
        iter_by_repeater,
        get_by_payload_id,
    ):
        payload_id = Mock()
        _get_repeat_record_ids(payload_id, None, 'test_domain', False)

        self.assertEqual(get_by_payload_id.call_count, 1)
        get_by_payload_id.assert_called_with(
            'test_domain', payload_id)
        self.assertEqual(iter_by_repeater.call_count, 0)

    @patch('corehq.apps.data_interfaces.tasks.get_couch_repeat_record_ids_by_payload_id')
    @patch('corehq.apps.data_interfaces.tasks.iter_repeat_record_ids_by_repeater')
    def test__get_ids_payload_id_not_in_data(
        self,
        iter_by_repeater,
        get_by_payload_id,
    ):
        REPEATER_ID = 'c0ffee'
        _get_repeat_record_ids(None, REPEATER_ID, 'test_domain', False)

        get_by_payload_id.assert_not_called()
        iter_by_repeater.assert_called_with(
            'test_domain', REPEATER_ID)
        self.assertEqual(iter_by_repeater.call_count, 1)

    @patch('corehq.motech.repeaters.models.RepeatRecord')
    def test__validate_record_record_does_not_exist(self, mock_RepeatRecord):
        mock_RepeatRecord.get.side_effect = [ResourceNotFound]
        response = _get_couch_repeat_record('test_domain', 'id_1')

        mock_RepeatRecord.get.assert_called_once()
        self.assertIsNone(response)

    @patch('corehq.motech.repeaters.models.RepeatRecord')
    def test__validate_record_invalid_domain(self, mock_RepeatRecord):
        mock_payload = Mock()
        mock_payload.domain = 'domain'
        mock_RepeatRecord.get.return_value = mock_payload
        response = _get_couch_repeat_record('test_domain', 'id_1')

        mock_RepeatRecord.get.assert_called_once()
        self.assertIsNone(response)

    @patch('corehq.motech.repeaters.models.RepeatRecord')
    def test__validate_record_success(self, mock_RepeatRecord):
        mock_payload = Mock()
        mock_payload.domain = 'test_domain'
        mock_RepeatRecord.get.return_value = mock_payload
        response = _get_couch_repeat_record('test_domain', 'id_1')

        mock_RepeatRecord.get.assert_called_once()
        self.assertEqual(response, mock_payload)


class TestTasks(TestCase):

    def setUp(self):
        self.mock_payload_one = Mock(id='id_1')
        self.mock_payload_two = Mock(id='id_2')
        self.mock_payload_ids = [self.mock_payload_one.id,
                                 self.mock_payload_two.id]

    @patch('corehq.apps.data_interfaces.tasks._get_repeat_record_ids')
    @patch('corehq.apps.data_interfaces.tasks.operate_on_payloads')
    def test_generate_ids_and_operate_on_payloads_success(
        self,
        mock_operate_on_payloads,
        mock__get_ids,
    ):
        payload_id = 'c0ffee'
        repeater_id = 'deadbeef'
        task_generate_ids_and_operate_on_payloads(
            payload_id, repeater_id, 'test_domain', 'test_action', False)

        mock__get_ids.assert_called_once()
        mock__get_ids.assert_called_with(
            'c0ffee', 'deadbeef', 'test_domain', False)

        mock_record_ids = mock__get_ids(
            'c0ffee', 'deadbeef', 'test_domain', False)
        mock_operate_on_payloads.assert_called_once()
        mock_operate_on_payloads.assert_called_with(
            mock_record_ids, 'test_domain', 'test_action', False,
            task=task_generate_ids_and_operate_on_payloads)

    @patch('corehq.apps.data_interfaces.utils.DownloadBase')
    @patch('corehq.apps.data_interfaces.utils._get_couch_repeat_record')
    def test_operate_on_payloads_no_task_from_excel_false_resend(
        self,
        mock__validate_record,
        mock_DownloadBase,
    ):
        mock__validate_record.side_effect = [self.mock_payload_one, None]

        response = operate_on_payloads(self.mock_payload_ids, 'test_domain',
                                       'resend', False)
        expected_response = {
            'messages': {
                'errors': [],
                'success': ['Successfully resent repeat record '
                            f'(id={self.mock_payload_one.id})'],
                'success_count_msg': "Successfully performed resend action on "
                                     "1 form(s)",
            }
        }

        self.assertEqual(mock_DownloadBase.set_progress.call_count, 0)
        self._check_resend(self.mock_payload_one, self.mock_payload_two,
                           response, expected_response)

    @patch('corehq.apps.data_interfaces.utils.DownloadBase')
    @patch('corehq.apps.data_interfaces.utils._get_couch_repeat_record')
    def test_operate_on_payloads_no_task_from_excel_true_resend(
        self,
        mock__validate_record,
        mock_DownloadBase,
    ):
        mock__validate_record.side_effect = [self.mock_payload_one, None]

        response = operate_on_payloads(self.mock_payload_ids, 'test_domain',
                                       'resend', False, from_excel=True)
        expected_response = {
            'errors': [],
            'success': ['Successfully resent repeat record '
                        f'(id={self.mock_payload_one.id})'],
        }

        self.assertEqual(mock_DownloadBase.set_progress.call_count, 0)
        self._check_resend(self.mock_payload_one, self.mock_payload_two,
                           response, expected_response)

    @patch('corehq.apps.data_interfaces.utils.DownloadBase')
    @patch('corehq.apps.data_interfaces.utils._get_couch_repeat_record')
    def test_operate_on_payloads_with_task_from_excel_false_resend(
        self,
        mock__validate_record,
        mock_DownloadBase,
    ):
        mock__validate_record.side_effect = [self.mock_payload_one, None]

        response = operate_on_payloads(self.mock_payload_ids, 'test_domain',
                                       'resend', False, task=Mock())
        expected_response = {
            'messages': {
                'errors': [],
                'success': ['Successfully resent repeat record '
                            f'(id={self.mock_payload_one.id})'],
                'success_count_msg': 'Successfully performed resend action on '
                                     '1 form(s)',
            }
        }

        self.assertEqual(mock_DownloadBase.set_progress.call_count, 2)
        self._check_resend(self.mock_payload_one, self.mock_payload_two,
                           response, expected_response)

    @patch('corehq.apps.data_interfaces.utils.DownloadBase')
    @patch('corehq.apps.data_interfaces.utils._get_couch_repeat_record')
    def test_operate_on_payloads_with_task_from_excel_true_resend(
        self,
        mock__validate_record,
        mock_DownloadBase,
    ):
        mock__validate_record.side_effect = [self.mock_payload_one, None]

        response = operate_on_payloads(self.mock_payload_ids, 'test_domain',
                                       'resend', False, task=Mock(),
                                       from_excel=True)
        expected_response = {
            'errors': [],
            'success': ['Successfully resent repeat record '
                        f'(id={self.mock_payload_one.id})'],
        }

        self.assertEqual(mock_DownloadBase.set_progress.call_count, 2)
        self._check_resend(self.mock_payload_one, self.mock_payload_two,
                           response, expected_response)

    @patch('corehq.apps.data_interfaces.utils.DownloadBase')
    @patch('corehq.apps.data_interfaces.utils._get_couch_repeat_record')
    def test_operate_on_payloads_no_task_from_excel_false_cancel(
        self,
        mock__validate_record,
        mock_DownloadBase,
    ):
        mock__validate_record.side_effect = [self.mock_payload_one, None]

        response = operate_on_payloads(self.mock_payload_ids, 'test_domain',
                                       'cancel', False)
        expected_response = {
            'messages': {
                'errors': [],
                'success': ['Successfully cancelled repeat record '
                            f'(id={self.mock_payload_one.id})'],
                'success_count_msg': 'Successfully performed cancel action on '
                                     '1 form(s)',
            }
        }

        self.assertEqual(mock_DownloadBase.set_progress.call_count, 0)
        self._check_cancel(self.mock_payload_one, self.mock_payload_two,
                           response, expected_response)

    @patch('corehq.apps.data_interfaces.utils.DownloadBase')
    @patch('corehq.apps.data_interfaces.utils._get_couch_repeat_record')
    def test_operate_on_payloads_no_task_from_excel_true_cancel(
        self,
        mock__validate_record,
        mock_DownloadBase,
    ):
        mock__validate_record.side_effect = [self.mock_payload_one, None]

        response = operate_on_payloads(self.mock_payload_ids, 'test_domain',
                                       'cancel', False, from_excel=True)
        expected_response = {
            'errors': [],
            'success': ['Successfully cancelled repeat record '
                        f'(id={self.mock_payload_one.id})'],
        }

        self.assertEqual(mock_DownloadBase.set_progress.call_count, 0)
        self._check_cancel(self.mock_payload_one, self.mock_payload_two,
                           response, expected_response)

    @patch('corehq.apps.data_interfaces.utils.DownloadBase')
    @patch('corehq.apps.data_interfaces.utils._get_couch_repeat_record')
    def test_operate_on_payloads_with_task_from_excel_false_cancel(
        self,
        mock__validate_record,
        mock_DownloadBase,
    ):
        mock__validate_record.side_effect = [self.mock_payload_one, None]

        response = operate_on_payloads(self.mock_payload_ids, 'test_domain',
                                       'cancel', False, task=Mock())
        expected_response = {
            'messages': {
                'errors': [],
                'success': ['Successfully cancelled repeat record '
                            f'(id={self.mock_payload_one.id})'],
                'success_count_msg': 'Successfully performed cancel action on '
                                     '1 form(s)',
            }
        }

        self.assertEqual(mock_DownloadBase.set_progress.call_count, 2)
        self._check_cancel(self.mock_payload_one, self.mock_payload_two,
                           response, expected_response)

    @patch('corehq.apps.data_interfaces.utils.DownloadBase')
    @patch('corehq.apps.data_interfaces.utils._get_couch_repeat_record')
    def test_operate_on_payloads_with_task_from_excel_true_cancel(
        self,
        mock__validate_record,
        mock_DownloadBase,
    ):
        mock__validate_record.side_effect = [self.mock_payload_one, None]

        response = operate_on_payloads(self.mock_payload_ids, 'test_domain',
                                       'cancel', False, task=Mock(),
                                       from_excel=True)
        expected_response = {
            'errors': [],
            'success': ['Successfully cancelled repeat record '
                        f'(id={self.mock_payload_one.id})'],
        }

        self.assertEqual(mock_DownloadBase.set_progress.call_count, 2)
        self._check_cancel(self.mock_payload_one, self.mock_payload_two,
                           response, expected_response)

    @patch('corehq.apps.data_interfaces.utils.DownloadBase')
    @patch('corehq.apps.data_interfaces.utils._get_couch_repeat_record')
    def test_operate_on_payloads_no_task_from_excel_false_requeue(
        self,
        mock__validate_record,
        mock_DownloadBase,
    ):
        mock__validate_record.side_effect = [self.mock_payload_one, None]

        response = operate_on_payloads(self.mock_payload_ids, 'test_domain',
                                       'requeue', False)
        expected_response = {
            'messages': {
                'errors': [],
                'success': ['Successfully requeued repeat record '
                            f'(id={self.mock_payload_one.id})'],
                'success_count_msg': 'Successfully performed requeue action '
                                     'on 1 form(s)',
            }
        }

        self.assertEqual(mock_DownloadBase.set_progress.call_count, 0)
        self._check_requeue(self.mock_payload_one, self.mock_payload_two,
                            response, expected_response)

    @patch('corehq.apps.data_interfaces.utils.DownloadBase')
    @patch('corehq.apps.data_interfaces.utils._get_couch_repeat_record')
    def test_operate_on_payloads_no_task_from_excel_true_requeue(
        self,
        mock__validate_record,
        mock_DownloadBase,
    ):
        mock__validate_record.side_effect = [self.mock_payload_one, None]

        response = operate_on_payloads(self.mock_payload_ids, 'test_domain',
                                       'requeue', False, from_excel=True)
        expected_response = {
            'errors': [],
            'success': [f'Successfully requeued repeat record '
                        f'(id={self.mock_payload_one.id})'],
        }

        self.assertEqual(mock_DownloadBase.set_progress.call_count, 0)
        self._check_requeue(self.mock_payload_one, self.mock_payload_two,
                            response, expected_response)

    @patch('corehq.apps.data_interfaces.utils.DownloadBase')
    @patch('corehq.apps.data_interfaces.utils._get_couch_repeat_record')
    def test_operate_on_payloads_with_task_from_excel_false_requeue(
        self,
        mock__validate_record,
        mock_DownloadBase,
    ):
        mock__validate_record.side_effect = [self.mock_payload_one, None]

        response = operate_on_payloads(self.mock_payload_ids, 'test_domain',
                                       'requeue', False, task=Mock())
        expected_response = {
            'messages': {
                'errors': [],
                'success': ['Successfully requeued repeat record '
                            f'(id={self.mock_payload_one.id})'],
                'success_count_msg': 'Successfully performed requeue action '
                                     'on 1 form(s)',
            }
        }

        self.assertEqual(mock_DownloadBase.set_progress.call_count, 2)
        self._check_requeue(self.mock_payload_one, self.mock_payload_two,
                            response, expected_response)

    @patch('corehq.apps.data_interfaces.utils.DownloadBase')
    @patch('corehq.apps.data_interfaces.utils._get_couch_repeat_record')
    def test_operate_on_payloads_with_task_from_excel_true_requeue(
        self,
        mock__validate_record,
        mock_DownloadBase,
    ):
        mock__validate_record.side_effect = [self.mock_payload_one, None]

        response = operate_on_payloads(self.mock_payload_ids, 'test_domain',
                                       'requeue', False, task=Mock(),
                                       from_excel=True)
        expected_response = {
            'errors': [],
            'success': ['Successfully requeued repeat record '
                        f'(id={self.mock_payload_one.id})'],
        }

        self.assertEqual(mock_DownloadBase.set_progress.call_count, 2)
        self._check_requeue(self.mock_payload_one, self.mock_payload_two,
                            response, expected_response)

    @patch('corehq.apps.data_interfaces.utils.DownloadBase')
    @patch('corehq.apps.data_interfaces.utils._get_couch_repeat_record')
    def test_operate_on_payloads_throws_exception_resend(
        self,
        mock__validate_record,
        mock_DownloadBase,
    ):
        mock__validate_record.side_effect = [self.mock_payload_one,
                                             self.mock_payload_two]
        self.mock_payload_two.fire.side_effect = [Exception('Boom!')]

        response = operate_on_payloads(self.mock_payload_ids, 'test_domain',
                                       'resend', False, task=Mock(),
                                       from_excel=True)
        expected_response = {
            'errors': ['Could not perform action for repeat record '
                       f'(id={self.mock_payload_two.id}): Boom!'],
            'success': ['Successfully resent repeat record '
                        f'(id={self.mock_payload_one.id})'],
        }

        self.assertEqual(mock_DownloadBase.set_progress.call_count, 3)
        self.assertEqual(self.mock_payload_one.fire.call_count, 1)
        self.assertEqual(self.mock_payload_two.fire.call_count, 1)
        self.assertEqual(response, expected_response)

    @patch('corehq.apps.data_interfaces.utils.DownloadBase')
    @patch('corehq.apps.data_interfaces.utils._get_couch_repeat_record')
    def test_operate_on_payloads_throws_exception_cancel(
        self,
        mock__validate_record,
        mock_DownloadBase,
    ):
        mock__validate_record.side_effect = [self.mock_payload_one,
                                             self.mock_payload_two]
        self.mock_payload_two.cancel.side_effect = [Exception('Boom!')]

        response = operate_on_payloads(self.mock_payload_ids, 'test_domain',
                                       'cancel', False, task=Mock(),
                                       from_excel=True)
        expected_response = {
            'errors': ['Could not perform action for repeat record '
                       f'(id={self.mock_payload_two.id}): Boom!'],
            'success': ['Successfully cancelled repeat record '
                        f'(id={self.mock_payload_one.id})'],
        }

        self.assertEqual(mock_DownloadBase.set_progress.call_count, 3)
        self.assertEqual(self.mock_payload_one.cancel.call_count, 1)
        self.assertEqual(self.mock_payload_one.save.call_count, 1)
        self.assertEqual(self.mock_payload_two.cancel.call_count, 1)
        self.assertEqual(self.mock_payload_two.save.call_count, 0)
        self.assertEqual(response, expected_response)

    @patch('corehq.apps.data_interfaces.utils.DownloadBase')
    @patch('corehq.apps.data_interfaces.utils._get_couch_repeat_record')
    def test_operate_on_payloads_throws_exception_requeue(
        self,
        mock__validate_record,
        mock_DownloadBase,
    ):
        mock__validate_record.side_effect = [self.mock_payload_one,
                                             self.mock_payload_two]
        self.mock_payload_two.requeue.side_effect = [Exception('Boom!')]

        response = operate_on_payloads(self.mock_payload_ids, 'test_domain',
                                       'requeue', False, task=Mock(),
                                       from_excel=True)
        expected_response = {
            'errors': ['Could not perform action for repeat record '
                       f'(id={self.mock_payload_two.id}): Boom!'],
            'success': ['Successfully requeued repeat record '
                        f'(id={self.mock_payload_one.id})'],
        }

        self.assertEqual(mock_DownloadBase.set_progress.call_count, 3)
        self.assertEqual(self.mock_payload_one.requeue.call_count, 1)
        self.assertEqual(self.mock_payload_one.save.call_count, 1)
        self.assertEqual(self.mock_payload_two.requeue.call_count, 1)
        self.assertEqual(self.mock_payload_two.save.call_count, 0)
        self.assertEqual(response, expected_response)

    def _check_resend(self, mock_payload_one, mock_payload_two,
                      response, expected_response):
        self.assertEqual(mock_payload_one.fire.call_count, 1)
        self.assertEqual(mock_payload_two.fire.call_count, 0)
        self.assertEqual(response, expected_response)

    def _check_cancel(self, mock_payload_one, mock_payload_two,
                      response, expected_response):
        self.assertEqual(mock_payload_one.cancel.call_count, 1)
        self.assertEqual(mock_payload_one.save.call_count, 1)
        self.assertEqual(mock_payload_two.cancel.call_count, 0)
        self.assertEqual(mock_payload_two.save.call_count, 0)
        self.assertEqual(response, expected_response)

    def _check_requeue(self, mock_payload_one, mock_payload_two,
                       response, expected_response):
        self.assertEqual(mock_payload_one.requeue.call_count, 1)
        self.assertEqual(mock_payload_one.save.call_count, 1)
        self.assertEqual(mock_payload_two.requeue.call_count, 0)
        self.assertEqual(mock_payload_two.save.call_count, 0)
        self.assertEqual(response, expected_response)


class TestGetRepeatRecordIDs(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.instance_id = str(uuid4())
        url = 'https://www.example.com/api/'
        conn = ConnectionSettings.objects.create(domain=DOMAIN, name=url, url=url)
        cls.repeater = FormRepeater(
            domain=DOMAIN,
            connection_settings_id=conn.id,
            include_app_id_param=False,
        )
        cls.repeater.save()
        cls.create_repeat_records()

    @classmethod
    def tearDownClass(cls):
        for record in cls.couch_records:
            record.delete(sync_to_sql=False)
        cls.repeater.delete()
        super().tearDownClass()

    @classmethod
    def create_repeat_records(cls):
        now = datetime.now()
        cls.couch_records = []
        cls.sql_records = []
        for __ in range(3):
            couch_record = RepeatRecord(
                domain=DOMAIN,
                repeater_id=cls.repeater.repeater_id,
                repeater_type='FormRepeater',
                payload_id=cls.instance_id,
                registered_on=now,
            )
            couch_record.save()
            cls.couch_records.append(couch_record)
        cls.sql_records = list(SQLRepeatRecord.objects.filter(
            domain=DOMAIN,
            repeater_id=cls.repeater.repeater_id,
        ))

    def test_no_payload_id_no_repeater_id_sql(self):
        result = _get_repeat_record_ids(payload_id=None, repeater_id=None,
                                        domain=DOMAIN, use_sql=True)
        self.assertEqual(result, [])

    def test_no_payload_id_no_repeater_id_couch(self):
        result = _get_repeat_record_ids(payload_id=None, repeater_id=None,
                                        domain=DOMAIN, use_sql=False)
        self.assertEqual(result, [])

    def test_payload_id_sql(self):
        result = _get_repeat_record_ids(payload_id=self.instance_id,
                                        repeater_id=None,
                                        domain=DOMAIN, use_sql=True)
        self.assertEqual(set(result), {r.pk for r in self.sql_records})

    def test_payload_id_couch(self):
        result = _get_repeat_record_ids(payload_id=self.instance_id,
                                        repeater_id=None,
                                        domain=DOMAIN, use_sql=False)
        self.assertEqual(set(result), {r._id for r in self.couch_records})

    def test_repeater_id_sql(self):
        result = _get_repeat_record_ids(payload_id=None,
                                        repeater_id=self.repeater.repeater_id,
                                        domain=DOMAIN, use_sql=True)
        self.assertEqual(set(result), {r.pk for r in self.sql_records})

    def test_repeater_id_couch(self):
        result = _get_repeat_record_ids(payload_id=None,
                                        repeater_id=self.repeater.repeater_id,
                                        domain=DOMAIN, use_sql=False)
        self.assertEqual(set(result), {r._id for r in self.couch_records})
