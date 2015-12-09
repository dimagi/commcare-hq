from django.test import SimpleTestCase
from ..log import clean_exception


class TestLogging(SimpleTestCase):
    def test_bad_traceback(self):
        result = "JJackson's SSN: 555-55-5555"
        try:
            # copied from couchdbkit/client.py
            assert isinstance(result, dict), 'received an invalid ' \
                'response of type %s: %s' % (type(result), repr(result))
        except AssertionError as e:
            pass
        self.assertIn(result, e.message)
        self.assertNotIn(result, clean_exception(e).message)

    def test_that_I_didnt_break_anything(self):
        exception = AssertionError("foo")
        cleaned_exception = clean_exception(exception)
        self.assertEqual(exception.__class__, cleaned_exception.__class__)
        self.assertEqual(exception.message, cleaned_exception.message)
