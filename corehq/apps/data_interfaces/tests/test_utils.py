from unittest.case import TestCase
from unittest.mock import patch, Mock

from couchdbkit import ResourceNotFound

from corehq.apps.data_interfaces.utils import _get_ids, _validate_record, generate_ids_and_operate_on_payloads, \
    operate_on_payloads


class TestUtils(TestCase):

    def test__get_ids_no_data(self):
        response = _get_ids('', 'test_domain')

        self.assertEqual(response, [])

    @patch('corehq.apps.data_interfaces.utils.get_repeat_records_by_payload_id')
    @patch('corehq.apps.data_interfaces.utils._get_startkey_endkey_all_records')
    def test__get_ids_payload_id_in_data(self, mock__get_startkey_endkey_all_records,
                                         mock_get_repeat_records_by_payload_id):
        data = {
            'payload_id': Mock()
        }
        response = _get_ids(data, 'test_domain')

        self.assertEqual(mock_get_repeat_records_by_payload_id.call_count, 1)
        mock_get_repeat_records_by_payload_id.assert_called_with('test_domain', data['payload_id'])
        self.assertEqual(mock__get_startkey_endkey_all_records.call_count, 0)

    @patch('corehq.apps.data_interfaces.utils.get_repeat_records_by_payload_id')
    @patch('corehq.apps.data_interfaces.utils._get_startkey_endkey_all_records')
    @patch('corehq.apps.data_interfaces.utils.RepeatRecord')
    def test__get_ids_payload_id_not_in_data(self, mock_RepeatRecord, mock__get_startkey_endkey_all_records,
                                             mock_get_repeat_records_by_payload_id):
        data = {
            'repeater': Mock()
        }
        mock_RepeatRecord.get_db.return_value.view.return_value.all.return_value = [
            {'id': 'id_1'},
            {'id': 'id_2'}
        ]
        response = _get_ids(data, 'test_domain')

        mock_get_repeat_records_by_payload_id.assert_not_called()
        mock__get_startkey_endkey_all_records.assert_called_with('test_domain', data['repeater'])
        self.assertEqual(mock__get_startkey_endkey_all_records.call_count, 1)
        self.assertEqual(response, ['id_1', 'id_2'])

    @patch('corehq.apps.data_interfaces.utils.RepeatRecord')
    def test__validate_record_record_does_not_exist(self, mock_RepeatRecord):
        mock_RepeatRecord.get.side_effect = [ResourceNotFound]
        response = _validate_record('id_1', 'test_domain')

        mock_RepeatRecord.get.assert_called_once()
        self.assertIsNone(response)

    @patch('corehq.apps.data_interfaces.utils.RepeatRecord')
    def test__validate_record_invalid_domain(self, mock_RepeatRecord):
        mock_payload = Mock()
        mock_payload.domain = 'domain'
        mock_RepeatRecord.get.return_value = mock_payload
        response = _validate_record('id_1', 'test_domain')

        mock_RepeatRecord.get.assert_called_once()
        self.assertIsNone(response)

    @patch('corehq.apps.data_interfaces.utils.RepeatRecord')
    def test__validate_record_success(self, mock_RepeatRecord):
        mock_payload = Mock()
        mock_payload.domain = 'test_domain'
        mock_RepeatRecord.get.return_value = mock_payload
        response = _validate_record('id_1', 'test_domain')

        mock_RepeatRecord.get.assert_called_once()
        self.assertEqual(response, mock_payload)

    @patch('corehq.apps.data_interfaces.utils._get_ids')
    @patch('corehq.apps.data_interfaces.utils.operate_on_payloads')
    def test_generate_ids_and_operate_on_payloads_success(self, mock_operate_on_payloads, mock__get_ids):
        mock_payload = Mock()
        mock_operate_on_payloads.return_value = 'success'
        response = generate_ids_and_operate_on_payloads(mock_payload, 'test_domain', 'test_action')

        mock__get_ids.assert_called_once()
        mock__get_ids.assert_called_with(mock_payload, 'test_domain')
        mock_payload_ids = mock__get_ids(mock_payload, 'test_domain')
        mock_operate_on_payloads.assert_called_once()
        mock_operate_on_payloads.assert_called_with(mock_payload_ids, 'test_domain', 'test_action', None, False)
        self.assertEqual(response, {'messages': 'success'})

    @patch('corehq.apps.data_interfaces.utils.DownloadBase')
    @patch('corehq.apps.data_interfaces.utils._validate_record')
    def test_operate_on_payloads_no_task_from_excel_false_resend(self, mock__validate_record, mock_DownloadBase):
        mock_payload_one, mock_payload_two = Mock(id='id_1'), Mock(id='id_2')
        mock_payload_ids = [mock_payload_one.id, mock_payload_two.id]
        mock__validate_record.side_effect = [mock_payload_one, None]

        with patch('corehq.apps.data_interfaces.utils._') as _:
            response = operate_on_payloads(mock_payload_ids, 'test_domain', 'resend')
            expected_response = {
                'messages': {
                    'errors': [],
                    'success': [_('Successfully resend payload (id={})').format(mock_payload_one.id)],
                    'success_count_msg': _("Successfully resend 1 form(s)")
                }
            }

        self.assertEqual(mock_DownloadBase.set_progress.call_count, 0)
        self._check_resend(mock_payload_one, mock_payload_two, response, expected_response)

    @patch('corehq.apps.data_interfaces.utils.DownloadBase')
    @patch('corehq.apps.data_interfaces.utils._validate_record')
    def test_operate_on_payloads_no_task_from_excel_true_resend(self, mock__validate_record, mock_DownloadBase):
        mock_payload_one, mock_payload_two = Mock(id='id_1'), Mock(id='id_2')
        mock_payload_ids = [mock_payload_one.id, mock_payload_two.id]
        mock__validate_record.side_effect = [mock_payload_one, None]

        with patch('corehq.apps.data_interfaces.utils._') as _:
            response = operate_on_payloads(mock_payload_ids, 'test_domain', 'resend', from_excel=True)
            expected_response = {
                'errors': [],
                'success': [_('Successfully resend payload (id={})').format(mock_payload_one.id)],
            }

        self.assertEqual(mock_DownloadBase.set_progress.call_count, 0)
        self._check_resend(mock_payload_one, mock_payload_two, response, expected_response)

    @patch('corehq.apps.data_interfaces.utils.DownloadBase')
    @patch('corehq.apps.data_interfaces.utils._validate_record')
    def test_operate_on_payloads_with_task_from_excel_false_resend(self, mock__validate_record, mock_DownloadBase):
        mock_payload_one, mock_payload_two = Mock(id='id_1'), Mock(id='id_2')
        mock_payload_ids = [mock_payload_one.id, mock_payload_two.id]
        mock__validate_record.side_effect = [mock_payload_one, None]

        with patch('corehq.apps.data_interfaces.utils._') as _:
            response = operate_on_payloads(mock_payload_ids, 'test_domain', 'resend', task=Mock())
            expected_response = {
                'messages': {
                    'errors': [],
                    'success': [_('Successfully resend payload (id={})').format(mock_payload_one.id)],
                    'success_count_msg': _("Successfully resend 1 form(s)")
                }
            }

        self.assertEqual(mock_DownloadBase.set_progress.call_count, 2)
        self._check_resend(mock_payload_one, mock_payload_two, response, expected_response)

    @patch('corehq.apps.data_interfaces.utils.DownloadBase')
    @patch('corehq.apps.data_interfaces.utils._validate_record')
    def test_operate_on_payloads_with_task_from_excel_true_resend(self, mock__validate_record, mock_DownloadBase):
        mock_payload_one, mock_payload_two = Mock(id='id_1'), Mock(id='id_2')
        mock_payload_ids = [mock_payload_one.id, mock_payload_two.id]
        mock__validate_record.side_effect = [mock_payload_one, None]

        with patch('corehq.apps.data_interfaces.utils._') as _:
            response = operate_on_payloads(mock_payload_ids, 'test_domain', 'resend', task=Mock(), from_excel=True)
            expected_response = {
                'errors': [],
                'success': [_('Successfully resend payload (id={})').format(mock_payload_one.id)],
            }

        self.assertEqual(mock_DownloadBase.set_progress.call_count, 2)
        self._check_resend(mock_payload_one, mock_payload_two, response, expected_response)

    @patch('corehq.apps.data_interfaces.utils.DownloadBase')
    @patch('corehq.apps.data_interfaces.utils._validate_record')
    def test_operate_on_payloads_no_task_from_excel_false_cancel(self, mock__validate_record, mock_DownloadBase):
        mock_payload_one, mock_payload_two = Mock(id='id_1'), Mock(id='id_2')
        mock_payload_ids = [mock_payload_one.id, mock_payload_two.id]
        mock__validate_record.side_effect = [mock_payload_one, None]

        with patch('corehq.apps.data_interfaces.utils._') as _:
            response = operate_on_payloads(mock_payload_ids, 'test_domain', 'cancel')
            expected_response = {
                'messages': {
                    'errors': [],
                    'success': [_('Successfully cancelled payload (id={})').format(mock_payload_one.id)],
                    'success_count_msg': _("Successfully cancel 1 form(s)")
                }
            }

        self.assertEqual(mock_DownloadBase.set_progress.call_count, 0)
        self._check_cancel(mock_payload_one, mock_payload_two, response, expected_response)

    @patch('corehq.apps.data_interfaces.utils.DownloadBase')
    @patch('corehq.apps.data_interfaces.utils._validate_record')
    def test_operate_on_payloads_no_task_from_excel_true_cancel(self, mock__validate_record, mock_DownloadBase):
        mock_payload_one, mock_payload_two = Mock(id='id_1'), Mock(id='id_2')
        mock_payload_ids = [mock_payload_one.id, mock_payload_two.id]
        mock__validate_record.side_effect = [mock_payload_one, None]

        with patch('corehq.apps.data_interfaces.utils._') as _:
            response = operate_on_payloads(mock_payload_ids, 'test_domain', 'cancel', from_excel=True)
            expected_response = {
                'errors': [],
                'success': [_('Successfully cancelled payload (id={})').format(mock_payload_one.id)],
            }

        self.assertEqual(mock_DownloadBase.set_progress.call_count, 0)
        self._check_cancel(mock_payload_one, mock_payload_two, response, expected_response)

    @patch('corehq.apps.data_interfaces.utils.DownloadBase')
    @patch('corehq.apps.data_interfaces.utils._validate_record')
    def test_operate_on_payloads_with_task_from_excel_false_cancel(self, mock__validate_record, mock_DownloadBase):
        mock_payload_one, mock_payload_two = Mock(id='id_1'), Mock(id='id_2')
        mock_payload_ids = [mock_payload_one.id, mock_payload_two.id]
        mock__validate_record.side_effect = [mock_payload_one, None]

        with patch('corehq.apps.data_interfaces.utils._') as _:
            response = operate_on_payloads(mock_payload_ids, 'test_domain', 'cancel', task=Mock())
            expected_response = {
                'messages': {
                    'errors': [],
                    'success': [_('Successfully cancelled payload (id={})').format(mock_payload_one.id)],
                    'success_count_msg': _("Successfully cancel 1 form(s)")
                }
            }

        self.assertEqual(mock_DownloadBase.set_progress.call_count, 2)
        self._check_cancel(mock_payload_one, mock_payload_two, response, expected_response)

    @patch('corehq.apps.data_interfaces.utils.DownloadBase')
    @patch('corehq.apps.data_interfaces.utils._validate_record')
    def test_operate_on_payloads_with_task_from_excel_true_cancel(self, mock__validate_record, mock_DownloadBase):
        mock_payload_one, mock_payload_two = Mock(id='id_1'), Mock(id='id_2')
        mock_payload_ids = [mock_payload_one.id, mock_payload_two.id]
        mock__validate_record.side_effect = [mock_payload_one, None]

        with patch('corehq.apps.data_interfaces.utils._') as _:
            response = operate_on_payloads(mock_payload_ids, 'test_domain', 'cancel', task=Mock(), from_excel=True)
            expected_response = {
                'errors': [],
                'success': [_('Successfully cancelled payload (id={})').format(mock_payload_one.id)],
            }

        self.assertEqual(mock_DownloadBase.set_progress.call_count, 2)
        self._check_cancel(mock_payload_one, mock_payload_two, response, expected_response)

    @patch('corehq.apps.data_interfaces.utils.DownloadBase')
    @patch('corehq.apps.data_interfaces.utils._validate_record')
    def test_operate_on_payloads_no_task_from_excel_false_requeue(self, mock__validate_record, mock_DownloadBase):
        mock_payload_one, mock_payload_two = Mock(id='id_1'), Mock(id='id_2')
        mock_payload_ids = [mock_payload_one.id, mock_payload_two.id]
        mock__validate_record.side_effect = [mock_payload_one, None]

        with patch('corehq.apps.data_interfaces.utils._') as _:
            response = operate_on_payloads(mock_payload_ids, 'test_domain', 'requeue')
            expected_response = {
                'messages': {
                    'errors': [],
                    'success': [_('Successfully requeue payload (id={})').format(mock_payload_one.id)],
                    'success_count_msg': _("Successfully requeue 1 form(s)")
                }
            }

        self.assertEqual(mock_DownloadBase.set_progress.call_count, 0)
        self._check_requeue(mock_payload_one, mock_payload_two, response, expected_response)

    @patch('corehq.apps.data_interfaces.utils.DownloadBase')
    @patch('corehq.apps.data_interfaces.utils._validate_record')
    def test_operate_on_payloads_no_task_from_excel_true_requeue(self, mock__validate_record, mock_DownloadBase):
        mock_payload_one, mock_payload_two = Mock(id='id_1'), Mock(id='id_2')
        mock_payload_ids = [mock_payload_one.id, mock_payload_two.id]
        mock__validate_record.side_effect = [mock_payload_one, None]

        with patch('corehq.apps.data_interfaces.utils._') as _:
            response = operate_on_payloads(mock_payload_ids, 'test_domain', 'requeue', from_excel=True)
            expected_response = {
                'errors': [],
                'success': [_('Successfully requeue payload (id={})').format(mock_payload_one.id)],
            }

        self.assertEqual(mock_DownloadBase.set_progress.call_count, 0)
        self._check_requeue(mock_payload_one, mock_payload_two, response, expected_response)

    @patch('corehq.apps.data_interfaces.utils.DownloadBase')
    @patch('corehq.apps.data_interfaces.utils._validate_record')
    def test_operate_on_payloads_with_task_from_excel_false_requeue(self, mock__validate_record, mock_DownloadBase):
        mock_payload_one, mock_payload_two = Mock(id='id_1'), Mock(id='id_2')
        mock_payload_ids = [mock_payload_one.id, mock_payload_two.id]
        mock__validate_record.side_effect = [mock_payload_one, None]

        with patch('corehq.apps.data_interfaces.utils._') as _:
            response = operate_on_payloads(mock_payload_ids, 'test_domain', 'requeue', task=Mock())
            expected_response = {
                'messages': {
                    'errors': [],
                    'success': [_('Successfully requeue payload (id={})').format(mock_payload_one.id)],
                    'success_count_msg': _("Successfully requeue 1 form(s)")
                }
            }

        self.assertEqual(mock_DownloadBase.set_progress.call_count, 2)
        self._check_requeue(mock_payload_one, mock_payload_two, response, expected_response)

    @patch('corehq.apps.data_interfaces.utils.DownloadBase')
    @patch('corehq.apps.data_interfaces.utils._validate_record')
    def test_operate_on_payloads_with_task_from_excel_true_requeue(self, mock__validate_record, mock_DownloadBase):
        mock_payload_one, mock_payload_two = Mock(id='id_1'), Mock(id='id_2')
        mock_payload_ids = [mock_payload_one.id, mock_payload_two.id]
        mock__validate_record.side_effect = [mock_payload_one, None]

        with patch('corehq.apps.data_interfaces.utils._') as _:
            response = operate_on_payloads(mock_payload_ids, 'test_domain', 'requeue', task=Mock(), from_excel=True)
            expected_response = {
                'errors': [],
                'success': [_('Successfully requeue payload (id={})').format(mock_payload_one.id)],
            }

        self.assertEqual(mock_DownloadBase.set_progress.call_count, 2)
        self._check_requeue(mock_payload_one, mock_payload_two, response, expected_response)

    @patch('corehq.apps.data_interfaces.utils.DownloadBase')
    @patch('corehq.apps.data_interfaces.utils._validate_record')
    def test_operate_on_payloads_throws_exception_resend(self, mock__validate_record, mock_DownloadBase):
        mock_payload_one, mock_payload_two = Mock(id='id_1'), Mock(id='id_2')
        mock_payload_ids = [mock_payload_one.id, mock_payload_two.id]
        mock__validate_record.side_effect = [mock_payload_one, mock_payload_two]
        mock_payload_two.fire.side_effect = [Exception]

        with patch('corehq.apps.data_interfaces.utils._') as _:
            response = operate_on_payloads(mock_payload_ids, 'test_domain', 'resend', task=Mock(), from_excel=True)
            expected_response = {
                'errors': [_("Could not perform action for payload (id={}): {}").format(mock_payload_two.id,
                                                                                        Exception)],
                'success': [_('Successfully requeue payload (id={})').format(mock_payload_one.id)],
            }

        self.assertEqual(mock_DownloadBase.set_progress.call_count, 3)
        self.assertEqual(mock_payload_one.fire.call_count, 1)
        self.assertEqual(mock_payload_two.fire.call_count, 1)
        self.assertEqual(response, expected_response)

    @patch('corehq.apps.data_interfaces.utils.DownloadBase')
    @patch('corehq.apps.data_interfaces.utils._validate_record')
    def test_operate_on_payloads_throws_exception_cancel(self, mock__validate_record, mock_DownloadBase):
        mock_payload_one, mock_payload_two = Mock(id='id_1'), Mock(id='id_2')
        mock_payload_ids = [mock_payload_one.id, mock_payload_two.id]
        mock__validate_record.side_effect = [mock_payload_one, mock_payload_two]
        mock_payload_two.cancel.side_effect = [Exception]

        with patch('corehq.apps.data_interfaces.utils._') as _:
            response = operate_on_payloads(mock_payload_ids, 'test_domain', 'cancel', task=Mock(), from_excel=True)
            expected_response = {
                'errors': [_("Could not perform action for payload (id={}): {}").format(mock_payload_two.id,
                                                                                        Exception)],
                'success': [_('Successfully cancelled payload (id={})').format(mock_payload_one.id)],
            }

        self.assertEqual(mock_DownloadBase.set_progress.call_count, 3)
        self.assertEqual(mock_payload_one.cancel.call_count, 1)
        self.assertEqual(mock_payload_one.save.call_count, 1)
        self.assertEqual(mock_payload_two.cancel.call_count, 1)
        self.assertEqual(mock_payload_two.save.call_count, 0)
        self.assertEqual(response, expected_response)

    @patch('corehq.apps.data_interfaces.utils.DownloadBase')
    @patch('corehq.apps.data_interfaces.utils._validate_record')
    def test_operate_on_payloads_throws_exception_requeue(self, mock__validate_record, mock_DownloadBase):
        mock_payload_one, mock_payload_two = Mock(id='id_1'), Mock(id='id_2')
        mock_payload_ids = [mock_payload_one.id, mock_payload_two.id]
        mock__validate_record.side_effect = [mock_payload_one, mock_payload_two]
        mock_payload_two.requeue.side_effect = [Exception]

        with patch('corehq.apps.data_interfaces.utils._') as _:
            response = operate_on_payloads(mock_payload_ids, 'test_domain', 'requeue', task=Mock(), from_excel=True)
            expected_response = {
                'errors': [_("Could not perform action for payload (id={}): {}").format(mock_payload_two.id,
                                                                                        Exception)],
                'success': [_('Successfully requeue payload (id={})').format(mock_payload_one.id)],
            }

        self.assertEqual(mock_DownloadBase.set_progress.call_count, 3)
        self.assertEqual(mock_payload_one.requeue.call_count, 1)
        self.assertEqual(mock_payload_one.save.call_count, 1)
        self.assertEqual(mock_payload_two.requeue.call_count, 1)
        self.assertEqual(mock_payload_two.save.call_count, 0)
        self.assertEqual(response, expected_response)

    def _check_resend(self, mock_payload_one, mock_payload_two, response, expected_response):
        self.assertEqual(mock_payload_one.fire.call_count, 1)
        self.assertEqual(mock_payload_two.fire.call_count, 0)
        self.assertEqual(response, expected_response)

    def _check_cancel(self, mock_payload_one, mock_payload_two, response, expected_response):
        self.assertEqual(mock_payload_one.cancel.call_count, 1)
        self.assertEqual(mock_payload_one.save.call_count, 1)
        self.assertEqual(mock_payload_two.cancel.call_count, 0)
        self.assertEqual(mock_payload_two.save.call_count, 0)
        self.assertEqual(response, expected_response)

    def _check_requeue(self, mock_payload_one, mock_payload_two, response, expected_response):
        self.assertEqual(mock_payload_one.requeue.call_count, 1)
        self.assertEqual(mock_payload_one.save.call_count, 1)
        self.assertEqual(mock_payload_two.requeue.call_count, 0)
        self.assertEqual(mock_payload_two.save.call_count, 0)
        self.assertEqual(response, expected_response)
