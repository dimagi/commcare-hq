from http.client import responses

from django.test import SimpleTestCase

from corehq.motech.repeater_helpers import RepeaterResponse
from corehq.motech.repeaters.models import get_repeater_response_from_submission_response
from corehq.util.test_utils import generate_cases
from couchforms.openrosa_response import ResponseNature

SUCCESS = f"""
    <OpenRosaResponse xmlns="http://openrosa.org/http/response">
        <message nature="{ResponseNature.SUBMIT_SUCCESS}">success</message>
    </OpenRosaResponse>
    """

V3_RETRY_ERROR = f"""
    <OpenRosaResponse xmlns="http://openrosa.org/http/response">
        <message nature="{ResponseNature.POST_PROCESSING_FAILURE}">success</message>
    </OpenRosaResponse>
    """

V3_ERROR = f"""
    <OpenRosaResponse xmlns="http://openrosa.org/http/response">
        <message nature="{ResponseNature.PROCESSING_FAILURE}">success</message>
    </OpenRosaResponse>
    """

V2_ERROR = f"""
    <OpenRosaResponse xmlns="http://openrosa.org/http/response">
        <message nature="{ResponseNature.SUBMIT_ERROR}">success</message>
    </OpenRosaResponse>
    """


class CommCareSubmissionResponseTests(SimpleTestCase):
    pass


@generate_cases([
    (201, SUCCESS, RepeaterResponse(201, 'Created', '')),
    (201, V2_ERROR, RepeaterResponse(422, ResponseNature.SUBMIT_ERROR, '', False)),
    (422, V3_ERROR, RepeaterResponse(422, ResponseNature.PROCESSING_FAILURE, '', False)),
    (422, V3_RETRY_ERROR, RepeaterResponse(422, ResponseNature.POST_PROCESSING_FAILURE, '', True)),
], CommCareSubmissionResponseTests)
def test_get_response(self, status_code, text, expected_response):
    response = get_repeater_response_from_submission_response(
        RepeaterResponse(status_code, responses[status_code], text)
    )
    self.assertEqual(response.status_code, expected_response.status_code)
    self.assertEqual(response.reason, expected_response.reason)
    self.assertEqual(response.retry, expected_response.retry)
