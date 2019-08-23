import requests_mock
from django.test import SimpleTestCase

from django.conf import settings

from corehq.apps.formplayer_api import const
from corehq.apps.formplayer_api.exceptions import FormplayerRequestException
from corehq.apps.formplayer_api.form_validation import validate_form


@requests_mock.Mocker()
class FormValidationTests(SimpleTestCase):
    def test_validation_success(self, mock):
        result = _get_validation_result(mock, {'problems': [], 'validated': True})
        self.assertTrue(result.success)

    def test_validation_fail(self, mock):
        problems = [
            {"message": "Problem 1", "fatal": False, "type": "dangerous"},
            {"message": "Problem 2", "fatal": False, "type": "error"}
        ]
        result = _get_validation_result(
            mock,
            api_response={
                "problems": problems,
                "fatal_error": "Fatal error",
                "fatal_error_expected": True,
                "validated": False
            }
        )
        self.assertFalse(result.success)
        self.assertEqual(result.fatal_error, 'Fatal error')
        self.assertEqual(result.problems, problems)

    def test_bad_status(self, mock):
        with self.assertRaises(FormplayerRequestException) as cm:
            _get_validation_result(mock, {}, status_code=500)

        self.assertEqual(cm.exception.status_code, 500)


def _get_validation_result(mock, api_response, status_code=200):
    mock.register_uri(
        'POST',
        settings.FORMPLAYER_URL + const.ENDPOINT_VALIDATE_FORM,
        json=api_response,
        status_code=status_code
    )
    result = validate_form('fake form')
    return result
