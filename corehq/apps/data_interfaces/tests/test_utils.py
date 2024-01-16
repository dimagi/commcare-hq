from datetime import datetime
from unittest.mock import Mock, patch
from uuid import uuid4

from django.test import SimpleTestCase, TestCase

from corehq.apps.data_interfaces.tasks import (
    _get_repeat_record_ids,
    task_generate_ids_and_operate_on_payloads,
)
from corehq.apps.data_interfaces.utils import (
    _get_sql_repeat_record,
    operate_on_payloads,
)
from corehq.motech.models import ConnectionSettings
from corehq.motech.repeaters.models import FormRepeater, SQLRepeatRecord

DOMAIN = 'test-domain'


class TestUtils(SimpleTestCase):

    def test__get_ids_no_data(self):
        response = _get_repeat_record_ids(None, None, 'test_domain')
        self.assertEqual(response, [])

    @patch('corehq.apps.data_interfaces.tasks.SQLRepeatRecord.objects.filter')
    def test__get_ids_payload_id_in_data(self, get_by_payload_id):
        payload_id = Mock()
        _get_repeat_record_ids(payload_id, None, 'test_domain')

        self.assertEqual(get_by_payload_id.call_count, 1)
        get_by_payload_id.assert_called_with(domain='test_domain', payload_id=payload_id)

    @patch('corehq.apps.data_interfaces.tasks.SQLRepeatRecord.objects.filter')
    def test__get_ids_payload_id_not_in_data(self, iter_by_repeater):
        REPEATER_ID = 'c0ffee'
        _get_repeat_record_ids(None, REPEATER_ID, 'test_domain')

        iter_by_repeater.assert_called_with(domain='test_domain', repeater__id=REPEATER_ID)
        self.assertEqual(iter_by_repeater.call_count, 1)

    @patch('corehq.motech.repeaters.models.SQLRepeatRecord.objects')
    def test__validate_record_record_does_not_exist(self, mock_objects):
        mock_objects.get.side_effect = [SQLRepeatRecord.DoesNotExist]
        response = _get_sql_repeat_record('test_domain', '1234')

        mock_objects.get.assert_called_once_with(domain='test_domain', id='1234')
        self.assertIsNone(response)

    @patch('corehq.motech.repeaters.models.SQLRepeatRecord.objects')
    def test__validate_record_invalid_domain(self, mock_objects):
        mock_objects.get.side_effect = SQLRepeatRecord.DoesNotExist
        response = _get_sql_repeat_record('test_domain', '1234')

        mock_objects.get.assert_called_once_with(domain='test_domain', id='1234')
        self.assertIsNone(response)

    @patch('corehq.motech.repeaters.models.SQLRepeatRecord.objects')
    def test__validate_record_success(self, mock_objects):
        mock_record = Mock()
        mock_record.domain = 'test_domain'
        mock_objects.get.return_value = mock_record
        response = _get_sql_repeat_record('test_domain', '1234')

        mock_objects.get.assert_called_once_with(domain='test_domain', id='1234')
        self.assertEqual(response, mock_record)


class TestTasks(TestCase):

    def setUp(self):
        self.mock_payload_one = Mock(id=1)
        self.mock_payload_two = Mock(id=2)
        self.mock_payload_ids = [self.mock_payload_one.id,
                                 self.mock_payload_two.id]

    @patch('corehq.apps.data_interfaces.tasks._get_repeat_record_ids')
    @patch('corehq.apps.data_interfaces.tasks.operate_on_payloads')
    def test_generate_ids_and_operate_on_payloads_success(
        self,
        mock_operate_on_payloads,
        mock__get_ids,
    ):
        mock__get_ids.return_value = record_ids = [1, 2, 3]
        payload_id = 'c0ffee'
        repeater_id = 'deadbeef'
        task_generate_ids_and_operate_on_payloads(
            payload_id, repeater_id, 'test_domain', 'test_action')

        mock__get_ids.assert_called_once()
        mock__get_ids.assert_called_with(
            'c0ffee', 'deadbeef', 'test_domain')

        mock_operate_on_payloads.assert_called_once()
        mock_operate_on_payloads.assert_called_with(
            record_ids, 'test_domain', 'test_action',
            task=task_generate_ids_and_operate_on_payloads)

    @patch('corehq.apps.data_interfaces.utils.DownloadBase')
    @patch('corehq.apps.data_interfaces.utils._get_sql_repeat_record')
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
    @patch('corehq.apps.data_interfaces.utils._get_sql_repeat_record')
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
    @patch('corehq.apps.data_interfaces.utils._get_sql_repeat_record')
    def test_operate_on_payloads_with_task_from_excel_false_resend(
        self,
        mock__validate_record,
        mock_DownloadBase,
    ):
        mock__validate_record.side_effect = [self.mock_payload_one, None]

        response = operate_on_payloads(self.mock_payload_ids, 'test_domain',
                                       'resend', task=Mock())
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
    @patch('corehq.apps.data_interfaces.utils._get_sql_repeat_record')
    def test_operate_on_payloads_with_task_from_excel_true_resend(
        self,
        mock__validate_record,
        mock_DownloadBase,
    ):
        mock__validate_record.side_effect = [self.mock_payload_one, None]

        response = operate_on_payloads(self.mock_payload_ids, 'test_domain',
                                       'resend', task=Mock(), from_excel=True)
        expected_response = {
            'errors': [],
            'success': ['Successfully resent repeat record '
                        f'(id={self.mock_payload_one.id})'],
        }

        self.assertEqual(mock_DownloadBase.set_progress.call_count, 2)
        self._check_resend(self.mock_payload_one, self.mock_payload_two,
                           response, expected_response)

    @patch('corehq.apps.data_interfaces.utils.DownloadBase')
    @patch('corehq.apps.data_interfaces.utils._get_sql_repeat_record')
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
    @patch('corehq.apps.data_interfaces.utils._get_sql_repeat_record')
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
    @patch('corehq.apps.data_interfaces.utils._get_sql_repeat_record')
    def test_operate_on_payloads_with_task_from_excel_false_cancel(
        self,
        mock__validate_record,
        mock_DownloadBase,
    ):
        mock__validate_record.side_effect = [self.mock_payload_one, None]

        response = operate_on_payloads(self.mock_payload_ids, 'test_domain',
                                       'cancel', task=Mock())
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
    @patch('corehq.apps.data_interfaces.utils._get_sql_repeat_record')
    def test_operate_on_payloads_with_task_from_excel_true_cancel(
        self,
        mock__validate_record,
        mock_DownloadBase,
    ):
        mock__validate_record.side_effect = [self.mock_payload_one, None]

        response = operate_on_payloads(self.mock_payload_ids, 'test_domain',
                                       'cancel', task=Mock(), from_excel=True)
        expected_response = {
            'errors': [],
            'success': ['Successfully cancelled repeat record '
                        f'(id={self.mock_payload_one.id})'],
        }

        self.assertEqual(mock_DownloadBase.set_progress.call_count, 2)
        self._check_cancel(self.mock_payload_one, self.mock_payload_two,
                           response, expected_response)

    @patch('corehq.apps.data_interfaces.utils.DownloadBase')
    @patch('corehq.apps.data_interfaces.utils._get_sql_repeat_record')
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
    @patch('corehq.apps.data_interfaces.utils._get_sql_repeat_record')
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
    @patch('corehq.apps.data_interfaces.utils._get_sql_repeat_record')
    def test_operate_on_payloads_with_task_from_excel_false_requeue(
        self,
        mock__validate_record,
        mock_DownloadBase,
    ):
        mock__validate_record.side_effect = [self.mock_payload_one, None]

        response = operate_on_payloads(self.mock_payload_ids, 'test_domain',
                                       'requeue', task=Mock())
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
    @patch('corehq.apps.data_interfaces.utils._get_sql_repeat_record')
    def test_operate_on_payloads_with_task_from_excel_true_requeue(
        self,
        mock__validate_record,
        mock_DownloadBase,
    ):
        mock__validate_record.side_effect = [self.mock_payload_one, None]

        response = operate_on_payloads(self.mock_payload_ids, 'test_domain',
                                       'requeue', task=Mock(), from_excel=True)
        expected_response = {
            'errors': [],
            'success': ['Successfully requeued repeat record '
                        f'(id={self.mock_payload_one.id})'],
        }

        self.assertEqual(mock_DownloadBase.set_progress.call_count, 2)
        self._check_requeue(self.mock_payload_one, self.mock_payload_two,
                            response, expected_response)

    @patch('corehq.apps.data_interfaces.utils.DownloadBase')
    @patch('corehq.apps.data_interfaces.utils._get_sql_repeat_record')
    def test_operate_on_payloads_throws_exception_resend(
        self,
        mock__validate_record,
        mock_DownloadBase,
    ):
        mock__validate_record.side_effect = [self.mock_payload_one,
                                             self.mock_payload_two]
        self.mock_payload_two.fire.side_effect = [Exception('Boom!')]

        response = operate_on_payloads(self.mock_payload_ids, 'test_domain',
                                       'resend', task=Mock(), from_excel=True)
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
    @patch('corehq.apps.data_interfaces.utils._get_sql_repeat_record')
    def test_operate_on_payloads_throws_exception_cancel(
        self,
        mock__validate_record,
        mock_DownloadBase,
    ):
        mock__validate_record.side_effect = [self.mock_payload_one,
                                             self.mock_payload_two]
        self.mock_payload_two.cancel.side_effect = [Exception('Boom!')]

        response = operate_on_payloads(self.mock_payload_ids, 'test_domain',
                                       'cancel', task=Mock(), from_excel=True)
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
    @patch('corehq.apps.data_interfaces.utils._get_sql_repeat_record')
    def test_operate_on_payloads_throws_exception_requeue(
        self,
        mock__validate_record,
        mock_DownloadBase,
    ):
        mock__validate_record.side_effect = [self.mock_payload_one,
                                             self.mock_payload_two]
        self.mock_payload_two.requeue.side_effect = [Exception('Boom!')]

        response = operate_on_payloads(self.mock_payload_ids, 'test_domain',
                                       'requeue', task=Mock(), from_excel=True)
        expected_response = {
            'errors': ['Could not perform action for repeat record '
                       f'(id={self.mock_payload_two.id}): Boom!'],
            'success': ['Successfully requeued repeat record '
                        f'(id={self.mock_payload_one.id})'],
        }

        self.assertEqual(mock_DownloadBase.set_progress.call_count, 3)
        self.assertEqual(self.mock_payload_one.requeue.call_count, 1)
        self.assertEqual(self.mock_payload_two.requeue.call_count, 1)
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
        self.assertEqual(mock_payload_two.requeue.call_count, 0)
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
    def create_repeat_records(cls):
        now = datetime.now()
        cls.sql_records = [SQLRepeatRecord(
            domain=DOMAIN,
            repeater_id=cls.repeater.id,
            payload_id=cls.instance_id,
            registered_at=now,
        ) for __ in range(3)]
        SQLRepeatRecord.objects.bulk_create(cls.sql_records)

    def test_no_payload_id_no_repeater_id_sql(self):
        result = _get_repeat_record_ids(payload_id=None, repeater_id=None, domain=DOMAIN)
        self.assertEqual(result, [])

    def test_payload_id_sql(self):
        result = _get_repeat_record_ids(payload_id=self.instance_id, repeater_id=None, domain=DOMAIN)
        self.assertEqual(set(result), {r.pk for r in self.sql_records})

    def test_repeater_id_sql(self):
        result = _get_repeat_record_ids(payload_id=None, repeater_id=self.repeater.repeater_id, domain=DOMAIN)
        self.assertEqual(set(result), {r.pk for r in self.sql_records})
