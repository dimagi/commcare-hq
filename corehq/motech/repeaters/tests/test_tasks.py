from collections import namedtuple
from contextlib import contextmanager
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.test import SimpleTestCase, TestCase

from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.form_processor.models import XFormInstance
from corehq.form_processor.utils.xform import (
    FormSubmissionBuilder,
    TestFormMetadata,
)
from corehq.motech.models import ConnectionSettings, RequestLog
from corehq.motech.repeaters.const import State
from corehq.motech.repeaters.models import FormRepeater, Repeater, RepeatRecord
from corehq.motech.repeaters.tasks import (
    _iter_ready_repeater_ids_once,
    _process_repeat_record,
    delete_old_request_logs,
    iter_ready_repeater_ids_forever,
    process_repeater,
    update_repeater,
)
from corehq.util.test_utils import _create_case

DOMAIN = 'gaidhlig'
PAYLOAD_IDS = ['aon', 'dha', 'trì', 'ceithir', 'coig', 'sia', 'seachd', 'ochd',
               'naoi', 'deich']


ResponseMock = namedtuple('ResponseMock', 'status_code reason')


class TestDeleteOldRequestLogs(TestCase):

    def test_raw_delete_logs_old(self):
        log = RequestLog.objects.create(domain=DOMAIN)
        log.timestamp = datetime.utcnow() - timedelta(days=43)
        log.save()  # Replace the value set by auto_now_add=True
        delete_old_request_logs.apply()

        count = RequestLog.objects.filter(domain=DOMAIN).count()
        self.assertEqual(count, 0)

    def test_raw_delete_logs_new(self):
        log = RequestLog.objects.create(domain=DOMAIN)
        log.timestamp = datetime.utcnow() - timedelta(days=41)
        log.save()
        delete_old_request_logs.apply()

        count = RequestLog.objects.filter(domain=DOMAIN).count()
        self.assertGreater(count, 0)

    def test_num_queries_per_chunk(self):
        log = RequestLog.objects.create(domain=DOMAIN)
        log.timestamp = datetime.utcnow() - timedelta(days=91)
        log.save()

        with self.assertNumQueries(3):
            delete_old_request_logs.apply()

    def test_num_queries_chunked(self):
        for __ in range(10):
            log = RequestLog.objects.create(domain=DOMAIN)
            log.timestamp = datetime.utcnow() - timedelta(days=91)
            log.save()

        with patch('corehq.motech.repeaters.tasks.DELETE_CHUNK_SIZE', 2):
            with self.assertNumQueries(11):
                delete_old_request_logs.apply()

        count = RequestLog.objects.filter(domain=DOMAIN).count()
        self.assertEqual(count, 0)


@contextmanager
def form_context(form_ids):
    for form_id in form_ids:
        builder = FormSubmissionBuilder(
            form_id=form_id,
            metadata=TestFormMetadata(domain=DOMAIN),
        )
        submit_form_locally(builder.as_xml_string(), DOMAIN)
    try:
        yield
    finally:
        XFormInstance.objects.hard_delete_forms(DOMAIN, form_ids)


class TestProcessRepeatRecord(TestCase):

    def test_fires_record(self):
        repeat_record = RepeatRecord.objects.create(
            domain=self.domain,
            payload_id='abc123',
            registered_at=datetime.utcnow(),
            repeater_id=self.repeater.repeater_id,
        )
        self.addCleanup(repeat_record.delete)

        _process_repeat_record(repeat_record.id)

        self.assertEqual(self.mock_fire.call_count, 1)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'process-repeat-record-tests'
        cls.conn_settings = ConnectionSettings.objects.create(
            domain=cls.domain,
            name='To Be Deleted',
            url="http://localhost/api/"
        )
        cls.addClassCleanup(cls.conn_settings.delete)
        cls.repeater = Repeater.objects.create(
            domain=cls.domain,
            connection_settings=cls.conn_settings,
        )
        cls.addClassCleanup(cls.repeater.delete)

    def setUp(self):
        self.patch()

    def patch(self):
        patch_fire = patch.object(RepeatRecord, 'fire')
        self.mock_fire = patch_fire.start()
        self.addCleanup(patch_fire.stop)


class TestIterReadyRepeaterIDsOnce(SimpleTestCase):

    @patch('corehq.motech.repeaters.tasks.rate_limit_repeater')
    @patch('corehq.motech.repeaters.tasks.Repeater.objects.get_all_ready_ids_by_domain')
    def test_round_robin(self, mock_get_all_ready, mock_rate_limit_repeater):
        mock_get_all_ready.return_value = {
            'domain1': ['repeater_id1', 'repeater_id2', 'repeater_id3'],
            'domain2': ['repeater_id4', 'repeater_id5'],
            'domain3': ['repeater_id6'],
        }
        mock_rate_limit_repeater.return_value = False
        pairs = list(_iter_ready_repeater_ids_once())
        self.assertEqual(pairs, [
            # First round of domains
            ('domain1', 'repeater_id1'),
            ('domain2', 'repeater_id4'),
            ('domain3', 'repeater_id6'),

            # Second round
            ('domain1', 'repeater_id2'),
            ('domain2', 'repeater_id5'),

            # Third round
            ('domain1', 'repeater_id3'),
        ])

    @patch('corehq.motech.repeaters.tasks.rate_limit_repeater')
    @patch('corehq.motech.repeaters.tasks.Repeater.objects.get_all_ready_ids_by_domain')
    def test_rate_limit(self, mock_get_all_ready, mock_rate_limit_repeater):
        mock_get_all_ready.return_value = {
            'domain1': ['repeater_id1', 'repeater_id2', 'repeater_id3'],
            'domain2': ['repeater_id4', 'repeater_id5'],
            'domain3': ['repeater_id6'],
        }
        mock_rate_limit_repeater.side_effect = lambda dom: dom == 'domain2'
        pairs = list(_iter_ready_repeater_ids_once())
        self.assertEqual(pairs, [
            ('domain1', 'repeater_id1'),
            ('domain3', 'repeater_id6'),
            ('domain1', 'repeater_id2'),
            ('domain1', 'repeater_id3'),
        ])


class TestIterReadyRepeaterIDsForever(SimpleTestCase):

    @patch('corehq.motech.repeaters.tasks.get_repeater_lock')
    @patch('corehq.motech.repeaters.tasks.rate_limit_repeater')
    @patch('corehq.motech.repeaters.tasks.Repeater.objects.get_all_ready_ids_by_domain')
    def test_successive_loops(self, mock_get_all_ready, mock_rate_limit_repeater, __):
        mock_get_all_ready.side_effect = [
            {
                'domain1': ['repeater_id1', 'repeater_id2', 'repeater_id3'],
                'domain2': ['repeater_id4', 'repeater_id5'],
                'domain3': ['repeater_id6'],
            },
            {
                'domain1': ['repeater_id1', 'repeater_id2'],
                'domain2': ['repeater_id4']
            },
            {},
        ]
        mock_rate_limit_repeater.return_value = False

        domain_repeater_id_tokens = iter_ready_repeater_ids_forever()
        domain_repeater_ids = [(t[0], t[1]) for t in domain_repeater_id_tokens]
        self.assertEqual(domain_repeater_ids, [
            # First loop
            ('domain1', 'repeater_id1'),
            ('domain2', 'repeater_id4'),
            ('domain3', 'repeater_id6'),
            ('domain1', 'repeater_id2'),
            ('domain2', 'repeater_id5'),
            ('domain1', 'repeater_id3'),

            # Second loop
            ('domain1', 'repeater_id1'),
            ('domain2', 'repeater_id4'),
            ('domain1', 'repeater_id2'),
        ])


class TestProcessRepeater(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.set_backoff_patch = patch.object(FormRepeater, 'set_backoff')
        cls.set_backoff_patch.start()

        cls.conn_settings = ConnectionSettings.objects.create(
            domain=DOMAIN,
            url='http://www.example.com/api/'
        )
        cls.repeater = FormRepeater.objects.create(
            domain=DOMAIN,
            connection_settings=cls.conn_settings,
        )

    @classmethod
    def tearDownClass(cls):
        cls.repeater.delete()
        cls.conn_settings.delete()
        cls.set_backoff_patch.stop()
        super().tearDownClass()

    def test_process_repeater_sends_repeat_record(self):
        payload, __ = _create_case(
            domain=DOMAIN,
            case_id=str(uuid4()),
            case_type='case',
            owner_id='abc123'
        )
        self.repeater.register(payload)

        with (
            patch('corehq.motech.repeaters.models.simple_request') as request_mock,
            patch('corehq.motech.repeaters.tasks.get_repeater_lock'),
        ):
            request_mock.return_value = ResponseMock(status_code=200, reason='OK')
            process_repeater(DOMAIN, self.repeater.repeater_id, 'token')

            request_mock.assert_called_once()

    def test_process_repeater_updates_repeater(self):
        payload, __ = _create_case(
            domain=DOMAIN,
            case_id=str(uuid4()),
            case_type='case',
            owner_id='abc123'
        )
        self.repeater.register(payload)

        with (
            patch('corehq.motech.repeaters.models.simple_request') as request_mock,
            patch('corehq.motech.repeaters.tasks.get_repeater_lock'),
        ):
            request_mock.return_value = ResponseMock(
                status_code=429,
                reason='Too Many Requests',
            )
            process_repeater(DOMAIN, self.repeater.repeater_id, 'token')

        self.repeater.set_backoff.assert_called_once()


class TestUpdateRepeater(SimpleTestCase):

    @patch('corehq.motech.repeaters.tasks.get_repeater_lock')
    @patch('corehq.motech.repeaters.tasks.Repeater.objects.get')
    def test_update_repeater_resets_backoff_on_success(self, mock_get_repeater, __):
        mock_repeater = MagicMock()
        mock_get_repeater.return_value = mock_repeater

        update_repeater([State.Success, State.Fail, State.Empty, None], 1, 'token')

        mock_repeater.set_backoff.assert_not_called()
        mock_repeater.reset_backoff.assert_called_once()

    @patch('corehq.motech.repeaters.tasks.get_repeater_lock')
    @patch('corehq.motech.repeaters.tasks.Repeater.objects.get')
    def test_update_repeater_sets_backoff_on_failure(self, mock_get_repeater, __):
        mock_repeater = MagicMock()
        mock_get_repeater.return_value = mock_repeater

        update_repeater([State.Fail, State.Empty, None], 1, 'token')

        mock_repeater.set_backoff.assert_called_once()
        mock_repeater.reset_backoff.assert_not_called()

    @patch('corehq.motech.repeaters.tasks.get_repeater_lock')
    @patch('corehq.motech.repeaters.tasks.Repeater.objects.get')
    def test_update_repeater_does_nothing_on_empty(self, mock_get_repeater, __):
        mock_repeater = MagicMock()
        mock_get_repeater.return_value = mock_repeater

        update_repeater([State.Empty], 1, 'token')

        mock_repeater.set_backoff.assert_not_called()
        mock_repeater.reset_backoff.assert_not_called()

    @patch('corehq.motech.repeaters.tasks.get_repeater_lock')
    @patch('corehq.motech.repeaters.tasks.Repeater.objects.get')
    def test_update_repeater_does_nothing_on_none(self, mock_get_repeater, __):
        mock_repeater = MagicMock()
        mock_get_repeater.return_value = mock_repeater

        update_repeater([None], 1, 'token')

        mock_repeater.set_backoff.assert_not_called()
        mock_repeater.reset_backoff.assert_not_called()

    @patch('corehq.motech.repeaters.tasks.get_repeater_lock')
    @patch('corehq.motech.repeaters.tasks.Repeater.objects.get')
    def test_update_repeater_releases_lock(self, mock_get_repeater, mock_get_repeater_lock):
        mock_get_repeater.side_effect = Exception()
        mock_lock = MagicMock()
        mock_get_repeater_lock.return_value = mock_lock

        with self.assertRaises(Exception):
            update_repeater([None], 1, 'token')

        mock_lock.release.assert_called_once()
