from django.test import SimpleTestCase

from corehq.util.test_utils import generate_cases
from couchforms.openrosa_response import parse_openrosa_response, ResponseNature

MESSAGE = "InvalidCaseIndex: Case 'X' references non-existent case 'Y'"
VALID = f"""
    <OpenRosaResponse xmlns="http://openrosa.org/http/response">
        <message nature="{ResponseNature.SUBMIT_ERROR}">
            {MESSAGE}
        </message>
    </OpenRosaResponse>
    """
INVALID = "<Anything></Anything>"
BAD_XML = """
    <OpenRosaResponse xmlns="http://openrosa.org/http/response">
    """


class TestOpenRosaResponse(SimpleTestCase):
    pass


@generate_cases([
    (VALID, ResponseNature.SUBMIT_ERROR, MESSAGE),
    (INVALID, None, None),
    (BAD_XML, None, None),
], TestOpenRosaResponse)
def test_parse_openrosa_response(self, xml, nature, message):
    response = parse_openrosa_response(xml)
    print(response)
    if message and nature:
        self.assertEqual(response.message, message)
        self.assertEqual(response.nature, nature)
    else:
        self.assertIsNone(response)
