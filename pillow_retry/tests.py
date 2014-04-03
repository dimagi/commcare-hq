import sys
from datetime import datetime
from pillow_retry.models import PillowError, name_path_from_object
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
    def test_id(self):
        id = '12345'
        error = create_error(id)
        self.assertEqual(error.original_id, id)
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


class ViewTests(TestCase):
    def setUp(self):
        self.db = PillowError.get_db()
        for row in self.db.view(
                "pillow_retry/pillow_errors",
                startkey=['created'],
                endkey=['created', {}],
                reduce=False
            ).all():
            self.db.delete_doc(row['id'])

    def test_get_errors_to_process(self):
        date = datetime.utcnow()
        for i in range(0, 5):
            error = create_error(id=i, attempts=i+1)
            error.date_next_attempt = date.replace(day=i+1)
            error.save()

        errors = PillowError.get_errors_to_process(
            date.replace(day=1),
            include_docs=True
        ).all()
        self.assertEqual(len(errors), 1)

        errors = PillowError.get_errors_to_process(
            date.replace(day=3),
            include_docs=True
        ).all()
        self.assertEqual(len(errors), 3)

    def test_get_errors(self):
        date = datetime.now()
        for i in range(0, 5):
            pillow = FakePillow() if i < 2 else FakePillow1()
            ex = ExceptionA if i < 3 else ExceptionB
            error = create_error(id=i, attempts=i+1, pillow=pillow, ex_class=ex)
            error.date_created = date.replace(day=i+1)
            error.save()

        errors = PillowError.get_errors(pillow=FakePillow(), include_docs=True)
        self.assertEqual(len(errors), 2)

        # query by pillow
        errors = PillowError.get_errors(pillow=FakePillow1(), startdate=date.replace(day=1),
                                     enddate=date.replace(day=4), include_docs=True)
        self.assertEqual(len(errors), 2)

        # query by error type
        errors = PillowError.get_errors(error_type=ExceptionA(), startdate=date.replace(day=2),
                                     enddate=date.replace(day=4), include_docs=True)
        self.assertEqual(len(errors), 2)

        # query by date
        errors = PillowError.get_errors(startdate=date.replace(day=2), enddate=date.replace(day=4), include_docs=True)
        self.assertEqual(len(errors), 3)

        # query by pillow and error
        errors = PillowError.get_errors(pillow=FakePillow1(), error_type=ExceptionA(), startdate=date.replace(day=1),
                                     enddate=date.replace(day=5), include_docs=True)
        self.assertEqual(len(errors), 1)




class FakePillow(BasicPillow):
    pass

class FakePillow1(BasicPillow):
    pass

class ExceptionA(Exception):
    pass

class ExceptionB(Exception):
    pass
