import sys
from datetime import datetime

from django.conf import settings
from django.test import TestCase
from six.moves import range

from pillow_retry.api import process_pillow_retry
from pillow_retry import const
from pillow_retry.models import PillowError
from pillowtop.checkpoints.manager import PillowCheckpoint
from pillowtop.feed.couch import change_from_couch_row
from pillowtop.feed.interface import Change, ChangeMeta
from pillowtop.feed.mock import RandomChangeFeed
from pillowtop.processors import PillowProcessor
from pillowtop.tests.utils import make_fake_constructed_pillow, FakeConstructedPillow


def get_ex_tb(message, ex_class=None):
    ex_class = ex_class if ex_class else ExceptionA
    try:
        raise ex_class(message)
    except Exception as e:
        return e, sys.exc_info()[2]


def FakePillow():
    return make_fake_constructed_pillow('FakePillow', 'fake-checkpoint')


def GetDocPillow():
    return FakeConstructedPillow(
        name='GetDocPillow',
        checkpoint=PillowCheckpoint('get_doc_processor', 'text'),
        change_feed=RandomChangeFeed(10),
        processor=GetDocProcessor(),
    )


class GetDocProcessor(PillowProcessor):
    """
    Processor that does absolutely nothing.
    """

    def process_change(self, change):
        doc = change.get_document()
        if not change.deleted and not doc:
            raise Exception('missing doc')


def create_error(change, message='message', attempts=0, pillow=None, ex_class=None):
    change.metadata = ChangeMeta(
        data_source_type='couch', data_source_name='test_commcarehq', document_id=change.id
    )
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
                'pillow_retry.tests.test_model.FakePillow',
                'pillow_retry.tests.test_model.GetDocPillow',
            ]
        }

    def tearDown(self):
        settings.PILLOWTOPS = self._pillowtops

    def test_id(self):
        id = '12345'
        change = Change(id=id, sequence_id=54321)
        error = create_error(change)
        self.assertEqual(error.doc_id, id)
        self.assertEqual(error.pillow, 'FakePillow')
        self.assertEqual(error.change_object.id, id)
        self.assertEqual(error.change_object.sequence_id, 54321)

    def test_attempts(self):
        message = 'ex message'
        error = create_error(_change(id='123'), message=message, attempts=1)
        self.assertEqual(error.total_attempts, 1)
        self.assertEqual(error.current_attempt, 1)
        self.assertTrue(message in error.error_traceback)
        self.assertEqual(error.error_type, 'pillow_retry.tests.test_model.ExceptionA')

        message = 'ex message2'
        error.add_attempt(*get_ex_tb(message))
        self.assertEqual(error.total_attempts, 2)
        self.assertEqual(error.current_attempt, 2)
        self.assertTrue(message in error.error_traceback)

    def test_get_or_create(self):
        message = 'abcd'
        id = '12335'
        error = create_error(_change(id=id), message=message, attempts=2)
        error.save()

        get = PillowError.get_or_create(_change(id=id), FakePillow())
        self.assertEqual(get.total_attempts, 2)
        self.assertEqual(get.current_attempt, 2)
        self.assertTrue(message in error.error_traceback)

        another_pillow = make_fake_constructed_pillow('FakePillow1', '')
        new = PillowError.get_or_create(_change(id=id), another_pillow)
        self.assertIsNone(new.id)
        self.assertEqual(new.current_attempt, 0)

    def test_get_errors_to_process(self):
        # Only re-process errors with
        # current_attempt < const.PILLOW_RETRY_QUEUE_MAX_PROCESSING_ATTEMPTS
        date = datetime.utcnow()
        for i in range(0, 5):
            error = create_error(_change(id=i), attempts=i+1)
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

    def test_get_errors_to_process_max_limit(self):
        date = datetime.utcnow()

        def make_error(id, current_attempt, total_attempts):
            error = create_error(_change(id=id))
            error.date_next_attempt = date
            error.current_attempt = current_attempt
            error.total_attempts = total_attempts
            error.save()

        # current_attempts <= limit, total_attempts <= limit
        make_error(
            'to-process1',
            const.PILLOW_RETRY_QUEUE_MAX_PROCESSING_ATTEMPTS,
            const.PILLOW_RETRY_MULTI_ATTEMPTS_CUTOFF
        )

        # current_attempts = 0, total_attempts > limit
        make_error(
            'to-process2',
            0,
            const.PILLOW_RETRY_MULTI_ATTEMPTS_CUTOFF + 1
        )

        # current_attempts > limit, total_attempts <= limit
        make_error(
            'not-processed1',
            const.PILLOW_RETRY_QUEUE_MAX_PROCESSING_ATTEMPTS + 1,
            const.PILLOW_RETRY_MULTI_ATTEMPTS_CUTOFF
        )

        # current_attempts <= limit, total_attempts > limit
        make_error(
            'not-processed2',
            const.PILLOW_RETRY_QUEUE_MAX_PROCESSING_ATTEMPTS,
            const.PILLOW_RETRY_MULTI_ATTEMPTS_CUTOFF + 1
        )

        errors = PillowError.get_errors_to_process(date).all()
        self.assertEqual(len(errors), 2)
        docs_to_process = {e.doc_id for e in errors}
        self.assertEqual({'to-process1', 'to-process2'}, docs_to_process)

    def test_deleted_doc(self):
        id = 'test_doc'
        change_dict = {'id': id, 'seq': 54321}
        error = create_error(change_from_couch_row(change_dict))
        error.save()
        # this used to error out
        process_pillow_retry(error)
        with self.assertRaises(PillowError.DoesNotExist):
            PillowError.objects.get(id=error.id)

    def test_bulk_reset(self):
        for i in range(0, 5):
            error = create_error(_change(id=i), attempts=const.PILLOW_RETRY_QUEUE_MAX_PROCESSING_ATTEMPTS)
            error.save()

        errors = PillowError.get_errors_to_process(datetime.utcnow()).all()
        self.assertEqual(len(errors), 0)

        PillowError.bulk_reset_attempts(datetime.utcnow())

        errors = PillowError.get_errors_to_process(datetime.utcnow()).all()
        self.assertEqual(len(errors), 5)

    def test_bulk_reset_cutoff(self):
        for i in range(0, 3):
            error = create_error(_change(id=i), attempts=1)
            if i >= 1:
                error.total_attempts = const.PILLOW_RETRY_MULTI_ATTEMPTS_CUTOFF + 1
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
        process_pillow_retry(error)
        # and that its total_attempts was bumped above the threshold
        error = PillowError.objects.get(pk=error.pk)
        self.assertTrue(error.total_attempts > const.PILLOW_RETRY_MULTI_ATTEMPTS_CUTOFF)

    def test_empty_metadata(self):
        change = _change(id='123')
        error = PillowError.get_or_create(change, GetDocPillow())
        error.save()

        process_pillow_retry(error)

        error = PillowError.objects.get(pk=error.id)
        self.assertEqual(error.total_attempts, 1)


class ExceptionA(Exception):
    pass


def _change(id):
    return Change(id=id, sequence_id=None)
