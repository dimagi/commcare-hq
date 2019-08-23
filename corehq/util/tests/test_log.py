
import six
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
        self.assertIn(result, six.text_type(exception))
        self.assertNotIn(result, six.text_type(clean_exception(exception)))

    def test_that_I_didnt_break_anything(self):
        exception = AssertionError("foo")
        cleaned_exception = clean_exception(exception)
        self.assertEqual(exception.__class__, cleaned_exception.__class__)
        self.assertEqual(six.text_type(exception), six.text_type(cleaned_exception))
