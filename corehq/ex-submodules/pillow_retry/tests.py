import sys
import uuid
from datetime import datetime

from dateutil.parser import parse
from django.conf import settings
from django.test import TestCase
from mock import MagicMock

from pillow_retry.models import PillowError
from pillow_retry.tasks import process_pillow_retry
from pillowtop import get_all_pillow_configs
from pillowtop.feed.interface import Change
from pillowtop.tests.utils import make_fake_constructed_pillow


def get_ex_tb(message, ex_class=None):
    ex_class = ex_class if ex_class else ExceptionA
    try:
        raise ex_class(message)
    except Exception as e:
        return e, sys.exc_info()[2]


def FakePillow():
    return make_fake_constructed_pillow('FakePillow', 'fake-checkpoint')


def create_error(change, message='message', attempts=0, pillow=None, ex_class=None):
    error = PillowError.get_or_create(change, pillow or FakePillow())
    for n in range(0, attempts):
        error.add_attempt(*get_ex_tb(message, ex_class=ex_class))
    return error


class PillowRetryTestCase(TestCase):

    def setUp(self):
        PillowError.objects.all().delete()
        self._pillowtops = settings.PILLOWTOPS
        settings.PILLOWTOPS = {
            'tests': [
                'pillow_retry.tests.FakePillow',
            ]
        }

    def tearDown(self):
        settings.PILLOWTOPS = self._pillowtops

    def test_id(self):
        id = '12345'
        change_dict = {'id': id, 'seq': 54321}
        error = create_error(change_dict)
        self.assertEqual(error.doc_id, id)
        self.assertEqual(error.pillow, 'FakePillow')
        self.assertEqual(error.change_object.id, id)
        self.assertEqual(error.change_object.sequence_id, 54321)

    def test_attempts(self):
        message = 'ex message'
        error = create_error({'id': '123'}, message=message, attempts=1)
        self.assertEqual(error.total_attempts, 1)
        self.assertEqual(error.current_attempt, 1)
        self.assertTrue(message in error.error_traceback)
        self.assertEqual(error.error_type, 'pillow_retry.tests.ExceptionA')

        message = 'ex message2'
        error.add_attempt(*get_ex_tb(message))
        self.assertEqual(error.total_attempts, 2)
        self.assertEqual(error.current_attempt, 2)
        self.assertTrue(message in error.error_traceback)

    def test_get_or_create(self):
        message = 'abcd'
        id = '12335'
        error = create_error({'id': id}, message=message, attempts=2)
        error.save()

        get = PillowError.get_or_create({'id': id}, FakePillow())
        self.assertEqual(get.total_attempts, 2)
        self.assertEqual(get.current_attempt, 2)
        self.assertTrue(message in error.error_traceback)

        another_pillow = make_fake_constructed_pillow('FakePillow1', '')
        new = PillowError.get_or_create({'id': id}, another_pillow)
        self.assertIsNone(new.id)
        self.assertEqual(new.current_attempt, 0)

    def test_get_errors_to_process(self):
        # Only re-process errors with
        # current_attempt < setting.PILLOW_RETRY_QUEUE_MAX_PROCESSING_ATTEMPTS
        date = datetime.utcnow()
        for i in range(0, 5):
            error = create_error({'id': i}, attempts=i+1)
            error.date_next_attempt = date.replace(day=i+1)
            error.save()

        errors = PillowError.get_errors_to_process(
            date.replace(day=1),
        ).all()
        self.assertEqual(len(errors), 1)

        errors = PillowError.get_errors_to_process(
            date.replace(day=5),
        ).all()
        self.assertEqual(len(errors), 3)

    def test_get_errors_to_process_queued(self):
        date = datetime.utcnow()
        error = create_error({'id': 1}, attempts=0)
        error.date_next_attempt = date
        error.save()

        queued_error = create_error({'id': 2}, attempts=0)
        queued_error.date_next_attempt = date
        queued_error.queued = True
        queued_error.save()

        errors = PillowError.get_errors_to_process(
            date,
        ).all()
        self.assertEqual(len(errors), 1)
        self.assertEqual(error.id, errors[0]['id'])

    def test_get_errors_to_process_queued_update(self):
        date = datetime.utcnow()
        error = create_error({'id': 1}, attempts=0)
        error.date_next_attempt = date
        error.save()

        errors = PillowError.get_errors_to_process(
            date,
        ).all()
        self.assertEqual(len(errors), 1)

        # check that calling update on the return value has the desired effect
        errors.update(queued=True)

        errors = PillowError.get_errors_to_process(
            date,
        ).all()
        self.assertEqual(len(errors), 0)

    def test_get_errors_to_process_max_limit(self):
        # see settings.PILLOW_RETRY_MULTI_ATTEMPTS_CUTOFF
        date = datetime.utcnow()

        def make_error(id, current_attempt, total_attempts):
            error = create_error({'id': id})
            error.date_next_attempt = date
            error.current_attempt = current_attempt
            error.total_attempts = total_attempts
            error.save()

        # current_attempts <= limit, total_attempts <= limit
        make_error(
            'to-process1',
            settings.PILLOW_RETRY_QUEUE_MAX_PROCESSING_ATTEMPTS,
            settings.PILLOW_RETRY_MULTI_ATTEMPTS_CUTOFF
        )

        # current_attempts = 0, total_attempts > limit
        make_error(
            'to-process2',
            0,
            settings.PILLOW_RETRY_MULTI_ATTEMPTS_CUTOFF + 1
        )

        # current_attempts > limit, total_attempts <= limit
        make_error(
            'not-processed1',
            settings.PILLOW_RETRY_QUEUE_MAX_PROCESSING_ATTEMPTS + 1,
            settings.PILLOW_RETRY_MULTI_ATTEMPTS_CUTOFF
        )

        # current_attempts <= limit, total_attempts > limit
        make_error(
            'not-processed2',
            settings.PILLOW_RETRY_QUEUE_MAX_PROCESSING_ATTEMPTS,
            settings.PILLOW_RETRY_MULTI_ATTEMPTS_CUTOFF + 1
        )

        errors = PillowError.get_errors_to_process(date, fetch_full=True).all()
        self.assertEqual(len(errors), 2)
        docs_to_process = {e.doc_id for e in errors}
        self.assertEqual({'to-process1', 'to-process2'}, docs_to_process)

    def test_deleted_doc(self):
        id = 'test_doc'
        change_dict = {'id': id, 'seq': 54321}
        error = create_error(change_dict)
        error.save()
        # this used to error out
        process_pillow_retry(error.id)
        with self.assertRaises(PillowError.DoesNotExist):
            PillowError.objects.get(id=error.id)

    def test_bulk_reset(self):
        for i in range(0, 5):
            error = create_error({'id': i}, attempts=settings.PILLOW_RETRY_QUEUE_MAX_PROCESSING_ATTEMPTS)
            error.save()

        errors = PillowError.get_errors_to_process(datetime.utcnow()).all()
        self.assertEqual(len(errors), 0)

        PillowError.bulk_reset_attempts(datetime.utcnow())

        errors = PillowError.get_errors_to_process(datetime.utcnow()).all()
        self.assertEqual(len(errors), 5)

    def test_bulk_reset_cutoff(self):
        for i in range(0, 3):
            error = create_error({'id': i}, attempts=1)
            if i >= 1:
                error.total_attempts = PillowError.multi_attempts_cutoff() + 1
            error.save()

        errors = PillowError.get_errors_to_process(datetime.utcnow()).all()
        self.assertEqual(len(errors), 0)

        PillowError.bulk_reset_attempts(datetime.utcnow())

        errors = PillowError.get_errors_to_process(datetime.utcnow()).all()
        self.assertEqual(len(errors), 2)

    def test_pillow_not_found(self):
        error = PillowError.objects.create(
            doc_id='missing-pillow',
            pillow='NotARealPillow',
            date_created=datetime.utcnow(),
            date_last_attempt=datetime.utcnow()
        )
        # make sure this doesn't error
        process_pillow_retry(error.id)
        # and that its total_attempts was bumped above the threshold
        self.assertTrue(PillowError.objects.get(pk=error.pk).total_attempts > PillowError.multi_attempts_cutoff())


class ExceptionA(Exception):
    pass


class PillowtopRetryAllPillowsTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls._PILLOWTOPS = settings.PILLOWTOPS
        if not settings.PILLOWTOPS:
            # assumes HqTestSuiteRunner, which blanks this out and saves a copy here
            settings.PILLOWTOPS = settings._PILLOWTOPS

    @classmethod
    def tearDownClass(cls):
        settings.PILLOWTOPS = cls._PILLOWTOPS

    def tearDown(self):
        PillowError.objects.all().delete()

    def test_all_pillows_handle_errors(self):
        all_pillow_configs = list(get_all_pillow_configs())
        for pillow_config in all_pillow_configs:
            self._test_error_logging_for_pillow(pillow_config)

    def _test_error_logging_for_pillow(self, pillow_config):
        pillow = _pillow_instance_from_config_with_mock_process_change(pillow_config)
        doc = self._get_random_doc()
        pillow.process_with_error_handling(Change(id=doc['id'], sequence_id='3', document=doc))

        errors = PillowError.objects.filter(pillow=pillow.pillow_id).all()
        self.assertEqual(1, len(errors), pillow_config)
        error = errors[0]
        self.assertEqual(error.doc_id, doc['id'], pillow_config)
        self.assertEqual('exceptions.Exception', error.error_type)
        self.assertIn(pillow.pillow_id, error.error_traceback)

    def _get_random_doc(self):
        return {
            'id': uuid.uuid4().hex,
            'doc_type': 'CommCareCase',
            'type': 'mother',
            'domain': 'pillow-retry-domain',
        }


def _pillow_instance_from_config_with_mock_process_change(pillow_config):
    pillow_class = pillow_config.get_class()
    if pillow_config.instance_generator is None:
        instance = pillow_class()
    else:
        instance = pillow_config.get_instance()

    instance.process_change = MagicMock(side_effect=Exception(instance.pillow_id))
    return instance
