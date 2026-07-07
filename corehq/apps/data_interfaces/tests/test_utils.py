from unittest.mock import Mock, patch

from django.test import SimpleTestCase, TestCase

from corehq.apps.data_interfaces.interfaces import FormManagementMode
from corehq.apps.data_interfaces.tasks import task_generate_ids_and_operate_on_payloads
from corehq.apps.data_interfaces.utils import (
    SKIPPED,
    SUCCEEDED,
    FormActionResult,
    apply_form_action,
    archive_or_restore_forms,
    operate_on_payloads,
)


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


class TestArchiveOrRestoreForms(SimpleTestCase):
    """Only intended to test how archive_or_restore_forms behaves"""

    USER_ID = 'user-id'
    USERNAME = 'user@example.com'

    def _archive_mode(self):
        return FormManagementMode(FormManagementMode.ARCHIVE_MODE)

    def _restore_mode(self):
        return FormManagementMode(FormManagementMode.RESTORE_MODE)

    def _patched_archive_or_restore_forms(
        self, mode, form_ids, forms, **kwargs
    ):
        with patch(
            'corehq.apps.data_interfaces.utils.XFormInstance.objects.iter_forms',
            return_value=forms,
        ):
            return archive_or_restore_forms(
                DOMAIN, self.USER_ID, self.USERNAME, form_ids, mode, **kwargs
            )

    def test_archive_success(self):
        form = Mock(form_id='f1', domain=DOMAIN)
        result = self._patched_archive_or_restore_forms(
            self._archive_mode(), ['f1'], [form]
        )
        form.archive.assert_called_once_with(user_id=self.USER_ID)
        messages = result['messages']
        assert messages['errors'] == []
        assert messages['success'] == [
            "Successfully archived XForm f1 for domain test-domain "
            "by user 'user@example.com'"
        ]
        assert messages['success_count_msg'] == 'Successfully archived  1 form(s)'

    def test_restore_success(self):
        form = Mock(form_id='f1', domain=DOMAIN)
        result = self._patched_archive_or_restore_forms(
            self._restore_mode(), ['f1'], [form]
        )
        form.unarchive.assert_called_once_with(user_id=self.USER_ID)
        messages = result['messages']
        assert messages['success'] == [
            "Successfully unarchived XForm f1 for domain test-domain "
            "by user 'user@example.com'"
        ]
        assert messages['success_count_msg'] == 'Successfully restored  1 form(s)'

    def test_missing_form_reported_not_found(self):
        result = self._patched_archive_or_restore_forms(
            self._archive_mode(), ['missing'], []
        )
        assert result['messages']['errors'] == ["Could not find XForm missing"]
        assert result['messages']['success'] == []

    def test_wrong_domain_reports_not_found(self):
        form = Mock(form_id='f1', domain='other-domain')
        result = self._patched_archive_or_restore_forms(
            self._archive_mode(), ['f1'], [form]
        )
        form.archive.assert_not_called()
        assert result['messages']['errors'] == ["Could not find XForm f1"]

    def test_action_exception_reported(self):
        form = Mock(form_id='f1', domain=DOMAIN)
        form.archive.side_effect = Exception('error')
        result = self._patched_archive_or_restore_forms(
            self._archive_mode(), ['f1'], [form]
        )
        assert result['messages']['errors'] == [
            "Could not archive XForm f1 for domain test-domain "
            "by user 'user@example.com': error"
        ]
        assert result['messages']['success'] == []

    def test_from_excel_returns_raw_response(self):
        form = Mock(form_id='f1', domain=DOMAIN)
        result = self._patched_archive_or_restore_forms(
            self._archive_mode(), ['f1'], [form], from_excel=True
        )
        assert 'messages' not in result
        assert 'success_count_msg' not in result
        assert result['success'] == [
            "Successfully archived XForm f1 for domain test-domain "
            "by user 'user@example.com'"
        ]
        assert result['errors'] == []


class TestApplyFormAction(SimpleTestCase):

    def _patched_apply_form_action(self, form_ids, forms, action_fn=None):
        action_fn = action_fn or (lambda xform: None)
        with patch(
            'corehq.apps.data_interfaces.utils.XFormInstance.objects.iter_forms',
            return_value=forms,
        ):
            return list(apply_form_action(DOMAIN, form_ids, action_fn))

    def test_empty_form_ids(self):
        assert self._patched_apply_form_action([], []) == []

    def test_success(self):
        form = Mock(form_id='f1', domain=DOMAIN)
        calls = []
        results = self._patched_apply_form_action(
            ['f1'], [form], action_fn=calls.append
        )
        assert calls == [form]
        assert results == [FormActionResult('f1', SUCCEEDED)]

    def test_missing_is_not_found(self):
        results = self._patched_apply_form_action(['missing'], [])
        assert results == [FormActionResult('missing', SKIPPED, 'not_found')]

    def test_wrong_domain_is_not_found(self):
        form = Mock(form_id='f1', domain='other-domain')
        called = []
        results = self._patched_apply_form_action(
            ['f1'], [form], action_fn=called.append
        )
        assert called == []  # action not applied to out-of-domain forms
        assert results == [FormActionResult('f1', SKIPPED, 'not_found')]

    def test_exception_is_unexpected_error(self):
        form = Mock(form_id='f1', domain=DOMAIN)

        def unexpected_error(xform):
            raise Exception('error')

        results = self._patched_apply_form_action(
            ['f1'], [form], action_fn=unexpected_error
        )
        assert results == [FormActionResult('f1', SKIPPED, 'unexpected_error')]

    def test_mixed_results(self):
        found = Mock(form_id='f1', domain=DOMAIN)
        results = self._patched_apply_form_action(['f1', 'missing'], [found])
        assert results == [
            FormActionResult('f1', SUCCEEDED),
            FormActionResult('missing', SKIPPED, 'not_found'),
        ]
