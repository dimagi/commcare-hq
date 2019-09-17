import imp
from datetime import datetime as dt

from couchdbkit import ResourceNotFound, ResourceConflict
from django.contrib.auth.models import User, Permission
from django.db import IntegrityError
from django.http import Http404, HttpResponse
from django.test import Client
from django.urls import reverse

from corehq.apps.users.decorators import require_can_edit_web_users
from django.views.decorators.http import require_POST

from corehq.apps.domain.models import Domain
from corehq.motech.repeaters.models import RepeatRecord, Repeater
from corehq.motech.repeaters.views import repeat_records
from unittest.mock import Mock, patch
from unittest.case import TestCase, skip

from dimagi.utils.web import json_response

_base_strings = [
    None,
    '',
    'repeater=&record_state=&payload_id=payload_3',
    'repeater=repeater_3&record_state=STATUS_2&payload_id=payload_2',
    'repeater=&record_state=&payload_id=',
    'repeater=repeater_1&record_state=STATUS_2&payload_id=payload_1',
    'repeater=&record_state=STATUS&payload_id=payload_2',
    'repeater=repeater_2&record_state=STATUS&payload_id=',
]


class TestRepeatRecordView(TestCase):

    def setUp(self):
        self.mock_domain = Domain.get_or_create_with_name('mock_domain', is_active=True)

        try:
            self.mock_user = User.objects.create_user(username='mock_user', password='mock_password')
        except IntegrityError:
            User.objects.get(username='mock_user').delete()
            self.mock_user = User.objects.create_user(username='mock_user', password='mock_password')

        def _create_record(record_id, payload_id, cancelled, succeeded):
            record_data = {
                '_id': record_id,
                'domain': self.mock_domain.name,
                'overall_tries': 0,
                'max_possible_tries': 5,
                'attempts': [],
                'registered_on': dt.now(),
                'last_checked': dt.now(),
                'failure_reason': 'None',
                'next_check': dt.now(),
                'repeater_id': 'repeater_id_1',
                'repeater_type': 'repeater_type_1',
                'payload_id': payload_id,
                'cancelled': False,
                'succeeded': False,
            }
            if cancelled:
                record_data['cancelled'] = True
            if succeeded:
                record_data['succeeded'] = True

            try:
                RepeatRecord(**record_data).save()
                mock_record = RepeatRecord.get(record_id)
            except ResourceConflict:
                RepeatRecord.get(record_id).delete()
                RepeatRecord(**record_data).save()
                mock_record = RepeatRecord.get(record_id)

            return mock_record

        self.mock_record_success = _create_record('id_1', 'payload_id_1', False, True)
        self.mock_record_cancelled = _create_record('id_2', 'payload_id_2', True, False)
        self.mock_record_pending = _create_record('id_3', 'payload_id_3', False, False)

        self.mock_client = Client()
        self.mock_client.login(username='mock_user', password='mock_password')

    def tearDown(self):
        mocks = [
            self.mock_client,
            self.mock_record_success,
            self.mock_record_cancelled,
            self.mock_record_pending,
            self.mock_user,
            self.mock_domain,
        ]

        for variable in mocks:
            try:
                variable.delete()
            except:
                continue

    @patch('corehq.motech.repeaters.views.repeat_records.RepeatRecord')
    def test_get_record_or_404(self, mock_RepeatRecord):
        domain = self.mock_domain.name
        record_id = self.mock_record_success.record_id
        domains = [domain, 'test_domain_2']
        records_ids = ['id_2', record_id]

        mock_RepeatRecord.get.side_effect = [self.mock_record_success, ResourceNotFound, self.mock_record_success]
        mock_RepeatRecord.domain = domains[0]

        record = repeat_records.RepeatRecordView.get_record_or_404(domain, record_id)
        assert record == self.mock_record_success

        for r in range(2):
            with self.assertRaises(Http404):
                mock_RepeatRecord.domain = domains[r]
                repeat_records.RepeatRecordView.get_record_or_404(domains[r], records_ids[r])

    @patch('corehq.motech.repeaters.views.repeat_records.RepeatRecordView.get_record_or_404')
    @patch('corehq.motech.repeaters.views.repeat_records.RepeatRecord')
    @patch('corehq.motech.repeaters.views.repeat_records.indent_xml')
    @patch('corehq.motech.repeaters.views.repeat_records.pformat_json')
    def test_get_with_payload_no_content_type(self, mock_pformat_json, mock_indent_xml,
                                              mock_RepeatRecord, mock_get_record_or_404):
        request = Mock()
        request.GET.get.return_value = self.mock_record_success.record_id
        mock_get_record_or_404.return_value = self.mock_record_success

        repeat_record_request = repeat_records.RepeatRecordView()
        with self.assertRaises(Exception):
            self.mock_client.get(repeat_record_request.get(request, self.mock_domain.name))

        mock_RepeatRecord.get_payload.assert_not_called()
        mock_indent_xml.assert_not_called()
        mock_pformat_json.assert_not_called()

    @patch('corehq.motech.repeaters.views.repeat_records._get_flag')
    @patch('corehq.motech.repeaters.views.repeat_records._schedule_task_with_flag')
    @patch('corehq.motech.repeaters.views.repeat_records._schedule_task_without_flag')
    def test_post_no_flag(self, mock__schedule_task_without_flag, mock__schedule_task_with_flag, mock__get_flag):
        domain = self.mock_domain.name
        request = Mock()
        request.GET.get.return_value = ''
        mock__get_flag.return_value = ''

        repeat_record_request = repeat_records.RepeatRecordView()
        response = repeat_record_request.post(request, domain)

        mock__get_flag.assert_called_with(request)
        mock__schedule_task_without_flag.assert_called_with(request, domain, 'resend')
        mock__schedule_task_with_flag.assert_not_called()

        assert response.status_code == 200

    @patch('corehq.motech.repeaters.views.repeat_records._get_flag')
    @patch('corehq.motech.repeaters.views.repeat_records._schedule_task_with_flag')
    @patch('corehq.motech.repeaters.views.repeat_records._schedule_task_without_flag')
    def test_post_with_flag(self, mock__schedule_task_without_flag, mock__schedule_task_with_flag, mock__get_flag):
        domain = self.mock_domain.name
        request = Mock()
        request.GET.get.return_value = 'flag'
        mock__get_flag.return_value = 'flag'

        repeat_record_request = repeat_records.RepeatRecordView()
        response = repeat_record_request.post(request, domain)

        mock__get_flag.assert_called_with(request)
        mock__schedule_task_without_flag.assert_not_called()
        mock__schedule_task_with_flag.assert_called_with(request, domain, 'resend')

        self.assertEqual(response.status_code, 200)

    @patch('corehq.motech.repeaters.views.repeat_records._get_flag')
    @patch('corehq.motech.repeaters.views.repeat_records._schedule_task_with_flag')
    @patch('corehq.motech.repeaters.views.repeat_records._schedule_task_without_flag')
    def test_cancel_repeat_record_requirements_not_satisfied(self, mock__schedule_task_without_flag,
                                                             mock__schedule_task_with_flag, mock__get_flag):
        domain = self.mock_domain.name
        request = Mock()

        response = repeat_records.cancel_repeat_record(request, domain)

        mock__get_flag.assert_not_called()
        mock__schedule_task_without_flag.assert_not_called()
        mock__schedule_task_with_flag.assert_not_called()

        self.assertEqual(response.status_code, 405)

    # @patch('corehq.motech.repeaters.views.repeat_records.require_POST', lambda x: x)
    # @patch('corehq.motech.repeaters.views.repeat_records.require_can_edit_web_users', lambda x: x)
    # @patch('corehq.motech.repeaters.views.repeat_records._get_flag')
    # @patch('corehq.motech.repeaters.views.repeat_records._schedule_task_with_flag')
    # @patch('corehq.motech.repeaters.views.repeat_records._schedule_task_without_flag')
    # def test_cancel_repeat_record_no_flag(self, mock__schedule_task_without_flag,
    #                                       mock__schedule_task_with_flag, mock__get_flag):
    #     domain = self.mock_domain.name
    #     request = Mock()
    #     request.GET.get.return_value = ''
    #     mock__get_flag.return_value = ''
    #
    #     response = self.mock_client.post(repeat_records.cancel_repeat_record(request, domain))
    #
    #     mock__get_flag.assert_called_with(request)
    #     mock__schedule_task_without_flag.assert_called()
    #     mock__schedule_task_without_flag.assert_called_with(request, domain, 'cancel')
    #     mock__schedule_task_with_flag.assert_not_called()
    #
    #     assert response.status_code == 200

    @patch('corehq.motech.repeaters.views.repeat_records._get_flag')
    @patch('corehq.motech.repeaters.views.repeat_records._schedule_task_with_flag')
    @patch('corehq.motech.repeaters.views.repeat_records._schedule_task_without_flag')
    def test_requeue_repeat_record_requirements_not_satisfied(self, mock__schedule_task_without_flag,
                                                              mock__schedule_task_with_flag, mock__get_flag):
        domain = self.mock_domain.name
        request = Mock()

        response = repeat_records.requeue_repeat_record(request, domain)

        mock__get_flag.assert_not_called()
        mock__schedule_task_without_flag.assert_not_called()
        mock__schedule_task_with_flag.assert_not_called()

        self.assertEqual(response.status_code, 405)


class TestUtilities(TestCase):
    _base_strings = [
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
            returned_string = repeat_records._change_record_state(self._base_strings[r], strings_to_add[r])
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
            returned_dict = repeat_records._url_parameters_to_dict(self._base_strings[r])
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
