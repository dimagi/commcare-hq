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
    _process_repeat_record,
    delete_old_request_logs,
    iter_ready_repeaters,
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
        repeater = Repeater.objects.create(
            domain=self.domain,
            connection_settings=self.conn_settings,
        )

        repeat_record = RepeatRecord(
            domain=self.domain,
            payload_id='abc123',
            registered_at=datetime.utcnow(),
            repeater_id=repeater.repeater_id,
        )

        _process_repeat_record(repeat_record)

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
        cls.repeater = Repeater.objects.create(
            domain=cls.domain,
            connection_settings=cls.conn_settings,
        )

    def setUp(self):
        self.patch()

    def patch(self):
        patch_fire = patch.object(RepeatRecord, 'fire')
        self.mock_fire = patch_fire.start()
        self.addCleanup(patch_fire.stop)


class TestIterReadyRepeaters(SimpleTestCase):

    def test_no_ready_repeaters(self):
        with (
            patch('corehq.motech.repeaters.tasks.Repeater.objects.all_ready',
                  return_value=[]),  # <--
            patch('corehq.motech.repeaters.models.domain_can_forward',
                  return_value=True),
            patch('corehq.motech.repeaters.tasks.rate_limit_repeater',
                  return_value=False)
        ):
            self.assertFalse(next(iter_ready_repeaters(), False))

    def test_not_domain_can_forward(self):
        with (
            patch('corehq.motech.repeaters.tasks.Repeater.objects.all_ready',
                  return_value=[Repeater()]),
            patch('corehq.motech.repeaters.models.domain_can_forward',
                  return_value=False),  # <--
            patch('corehq.motech.repeaters.tasks.rate_limit_repeater',
                  return_value=False)
        ):
            self.assertFalse(next(iter_ready_repeaters(), False))

    def test_pause_data_forwarding(self):
        with (
            patch('corehq.motech.repeaters.tasks.Repeater.objects.all_ready',
                  return_value=[Repeater()]),
            patch('corehq.motech.repeaters.models.domain_can_forward',
                  return_value=True),
            patch('corehq.motech.repeaters.tasks.rate_limit_repeater',
                  return_value=False),
            patch('corehq.motech.repeaters.models.toggles.PAUSE_DATA_FORWARDING.enabled',
                  return_value=True)  # <--
        ):
            self.assertFalse(next(iter_ready_repeaters(), False))

    def test_rate_limit_repeater(self):
        with (
            patch('corehq.motech.repeaters.tasks.Repeater.objects.all_ready',
                  return_value=[Repeater()]),
            patch('corehq.motech.repeaters.models.domain_can_forward',
                  return_value=True),
            patch('corehq.motech.repeaters.tasks.rate_limit_repeater',
                  return_value=True),  # <--
            patch.object(Repeater, 'rate_limit')
        ):
            self.assertFalse(next(iter_ready_repeaters(), False))

    def test_successive_loops(self):
        repeater_1 = Repeater()
        repeater_2 = Repeater()
        with (
            patch('corehq.motech.repeaters.tasks.Repeater.objects.all_ready',
                  side_effect=[[repeater_1, repeater_2], [repeater_1], []]),
            patch('corehq.motech.repeaters.models.domain_can_forward',
                  return_value=True),
            patch('corehq.motech.repeaters.tasks.rate_limit_repeater',
                  return_value=False),
            patch('corehq.motech.repeaters.tasks.get_repeater_lock')
        ):
            repeaters = list(iter_ready_repeaters())
            self.assertEqual(len(repeaters), 3)
            self.assertEqual(repeaters, [repeater_1, repeater_2, repeater_1])


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
            patch('corehq.motech.repeaters.tasks.get_repeater_lock')
        ):
            request_mock.return_value = ResponseMock(status_code=200, reason='OK')
            process_repeater(DOMAIN, self.repeater.repeater_id)

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
            patch('corehq.motech.repeaters.tasks.get_repeater_lock')
        ):
            request_mock.return_value = ResponseMock(status_code=404, reason='Not found')
            process_repeater(DOMAIN, self.repeater.repeater_id)

        self.repeater.set_backoff.assert_called_once()


class TestUpdateRepeater(SimpleTestCase):

    @patch('corehq.motech.repeaters.tasks.Repeater.objects.get')
    def test_update_repeater_resets_backoff_on_success(self, mock_get_repeater):
        mock_repeater = MagicMock()
        mock_get_repeater.return_value = mock_repeater

        with patch('corehq.motech.repeaters.tasks.get_repeater_lock'):
            update_repeater([State.Success, State.Fail, State.Empty, None], 1)

        mock_repeater.set_backoff.assert_not_called()
        mock_repeater.reset_backoff.assert_called_once()

    @patch('corehq.motech.repeaters.tasks.Repeater.objects.get')
    def test_update_repeater_sets_backoff_on_failure(self, mock_get_repeater):
        mock_repeater = MagicMock()
        mock_get_repeater.return_value = mock_repeater

        with patch('corehq.motech.repeaters.tasks.get_repeater_lock'):
            update_repeater([State.Fail, State.Empty, None], 1)

        mock_repeater.set_backoff.assert_called_once()
        mock_repeater.reset_backoff.assert_not_called()

    @patch('corehq.motech.repeaters.tasks.Repeater.objects.get')
    def test_update_repeater_does_nothing_on_empty(self, mock_get_repeater):
        mock_repeater = MagicMock()
        mock_get_repeater.return_value = mock_repeater

        with patch('corehq.motech.repeaters.tasks.get_repeater_lock'):
            update_repeater([State.Empty], 1)

        mock_repeater.set_backoff.assert_not_called()
        mock_repeater.reset_backoff.assert_not_called()

    @patch('corehq.motech.repeaters.tasks.Repeater.objects.get')
    def test_update_repeater_does_nothing_on_none(self, mock_get_repeater):
        mock_repeater = MagicMock()
        mock_get_repeater.return_value = mock_repeater

        with patch('corehq.motech.repeaters.tasks.get_repeater_lock'):
            update_repeater([None], 1)

        mock_repeater.set_backoff.assert_not_called()
        mock_repeater.reset_backoff.assert_not_called()
