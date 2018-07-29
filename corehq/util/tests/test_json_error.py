from __future__ import absolute_import
from __future__ import unicode_literals
from django.test.testcases import SimpleTestCase

from corehq.util.test_utils import generate_cases
from corehq.util.view_utils import _json_exception_response_data


class JsonErrorTests(SimpleTestCase):
    """Test json_error decorator"""


@generate_cases([
    (b'ascii string',),
    (b'utf8 string \xef\xbd\xa1', 'utf8 string \uff61'),
    ('unicode string \uff61',),
], JsonErrorTests)
def test_json_exception_response_data(self, message, expected=None):
    data = _json_exception_response_data(500, Exception(message))
    self.assertEqual(data['message'], expected or message)
