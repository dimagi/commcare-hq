import sys
from datetime import datetime
from pillow_retry.models import PillowError, path_from_object
from django.test import TestCase
from pillowtop.listener import BasicPillow

def get_ex_tb(message, ex_class=None):
    ex_class = ex_class if ex_class else ExceptionA
    try:
        raise ex_class(message)
    except Exception as e:
        return e, sys.exc_info()[2]


def create_error(id='123', message='message', attempts=0, pillow=None, ex_class=None):
    error = PillowError.get_or_create({'id': id}, pillow or FakePillow())
    for n in range(0, attempts):
        error.add_attempt(*get_ex_tb(message, ex_class=ex_class))
    return error


class PillowRetryTestCase(TestCase):
    def setUp(self):
        PillowError.objects.all().delete()

    def test_id(self):
        id = '12345'
        error = create_error(id)
        self.assertEqual(error.doc_id, id)
        self.assertEqual(error.pillow, 'pillow_retry.tests.FakePillow')

    def test_attempts(self):
        message = 'ex message'
        error = create_error(message=message, attempts=1)
        self.assertEqual(error.total_attempts, 1)
        self.assertEqual(error.current_attempt, 1)
        self.assertEqual(error.error_message, message)
        self.assertEqual(error.error_type, 'pillow_retry.tests.ExceptionA')

        message = 'ex message2'
        error.add_attempt(*get_ex_tb(message))
        self.assertEqual(error.total_attempts, 2)
        self.assertEqual(error.current_attempt, 2)
        self.assertEqual(error.error_message, message)

    def test_get_or_create(self):
        message = 'abcd'
        id = '12335'
        error = create_error(id, message=message, attempts=2)
        error.save()

        get = PillowError.get_or_create({'id': id}, FakePillow())
        self.assertEqual(get.total_attempts, 2)
        self.assertEqual(get.current_attempt, 2)
        self.assertEqual(get.error_message, message)

        new = PillowError.get_or_create({'id': id}, FakePillow1())
        self.assertIsNone(new.id)
        self.assertEqual(new.current_attempt, 0)

    def test_get_errors_to_process(self):
        date = datetime.utcnow()
        for i in range(0, 5):
            error = create_error(id=i, attempts=i+1)
            error.date_next_attempt = date.replace(day=i+1)
            error.save()

        errors = PillowError.get_errors_to_process(
            date.replace(day=1),
        ).all()
        self.assertEqual(len(errors), 1)

        errors = PillowError.get_errors_to_process(
            date.replace(day=3),
        ).all()
        self.assertEqual(len(errors), 3)


class FakePillow(BasicPillow):
    pass

class FakePillow1(BasicPillow):
    pass

class ExceptionA(Exception):
    pass