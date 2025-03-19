from unittest.mock import Mock, patch

from django.test import TestCase

from corehq.apps.data_interfaces.tasks import task_generate_ids_and_operate_on_payloads
from corehq.apps.data_interfaces.utils import operate_on_payloads


DOMAIN = 'test-domain'


class TestTasks(TestCase):

    def setUp(self):
        self.mock_payload_one = Mock(id=1)
        self.mock_payload_two = Mock(id=2)
        self.mock_payload_ids = [self.mock_payload_one.id,
                                 self.mock_payload_two.id]

    @patch('corehq.apps.data_interfaces.tasks.RepeatRecord.objects.get_repeat_record_ids')
    @patch('corehq.apps.data_interfaces.tasks.operate_on_payloads')
    def test_generate_ids_and_operate_on_payloads_success(
        self,
        mock_operate_on_payloads,
        mock_get_repeat_record_ids,
    ):
        mock_get_repeat_record_ids.return_value = record_ids = [1, 2, 3]
        payload_id = 'c0ffee'
        repeater_id = 'deadbeef'
        task_generate_ids_and_operate_on_payloads(
            payload_id, repeater_id, 'test_domain', 'test_action')

        mock_get_repeat_record_ids.assert_called_once()
        mock_get_repeat_record_ids.assert_called_with(
            'test_domain', repeater_id='deadbeef', state=None, payload_id='c0ffee')

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
