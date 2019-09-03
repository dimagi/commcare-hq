from django.test import SimpleTestCase
from ..log import clean_exception


class TestLogging(SimpleTestCase):

    def test_bad_traceback(self):
        result = "JJackson's SSN: 555-55-5555"
        exception = None
        try:
            # copied from couchdbkit/client.py
            assert isinstance(result, dict), 'received an invalid ' \
                'response of type %s: %s' % (type(result), repr(result))
        except AssertionError as e:
            exception = e
        self.assertIn(result, str(exception))
        self.assertNotIn(result, str(clean_exception(exception)))

    def test_that_I_didnt_break_anything(self):
        exception = AssertionError("foo")
        cleaned_exception = clean_exception(exception)
        self.assertEqual(exception.__class__, cleaned_exception.__class__)
        self.assertEqual(str(exception), str(cleaned_exception))
