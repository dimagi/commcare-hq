import sys
from datetime import datetime, timedelta
from dateutil.parser import parse
from django.conf import settings
from pillow_retry.models import PillowError, Stub
from django.test import TestCase
from pillow_retry.tasks import process_pillow_retry
from pillowtop.couchdb import CachedCouchDB
from pillowtop.listener import BasicPillow


def get_ex_tb(message, ex_class=None):
    ex_class = ex_class if ex_class else ExceptionA
    try:
        raise ex_class(message)
    except Exception as e:
        return e, sys.exc_info()[2]


def create_error(change, message='message', attempts=0, pillow=None, ex_class=None):
    error = PillowError.get_or_create(change, pillow or FakePillow())
    for n in range(0, attempts):
        error.add_attempt(*get_ex_tb(message, ex_class=ex_class))
    return error


class PillowRetryTestCase(TestCase):
    def setUp(self):
        PillowError.objects.all().delete()

    def test_id(self):
        id = '12345'
        change_dict = {'id': id, 'seq': 54321, 'changes': [{'_rev': 'abc123'}]}
        error = create_error(change_dict)
        self.assertEqual(error.doc_id, id)
        self.assertEqual(error.pillow, 'pillow_retry.tests.FakePillow')
        self.assertEqual(error.change_dict, change_dict)


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

        new = PillowError.get_or_create({'id': id}, FakePillow1())
        self.assertIsNone(new.id)
        self.assertEqual(new.current_attempt, 0)

    def test_get_or_create_meta(self):
        id = '12335'
        date = '2013-12-05T08:52:19Z'
        meta = {
            'domains': ['a' * 247, '123456789'],
            'doc_type': 'something',
            'date': date,
        }
        get = PillowError.get_or_create({'id': id}, FakePillow(), meta)
        self.assertEqual(get.domains, 'a' * 247 + ',1234...')
        self.assertEqual(get.doc_type, 'something')
        self.assertEqual(get.doc_date, parse(date))
        get.save()

    def test_get_errors_to_process(self):
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
            date.replace(day=3),
        ).all()

    def test_include_doc(self):
        id = 'test_doc'
        FakePillow.couch_db._docs[id] = {'id': id, 'property': 'value'}
        change_dict = {'id': id, 'seq': 54321, 'changes': [{'_rev': 'abc123'}]}
        error = create_error(change_dict)
        error.save()
        process_pillow_retry(error.id)

        with self.assertRaises(PillowError.DoesNotExist):
            #  if processing is successful the record will be deleted
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


class FakePillow(BasicPillow):
    couch_db = CachedCouchDB(Stub.get_db().uri, readonly=True)

    def process_change(self, change, is_retry_attempt=False):
        #  see test_include_doc
        if 'doc' not in change:
            raise Exception('missing doc in change')


class FakePillow1(BasicPillow):
    couch_db = CachedCouchDB(Stub.get_db().uri, readonly=True)


class ExceptionA(Exception):
    pass
