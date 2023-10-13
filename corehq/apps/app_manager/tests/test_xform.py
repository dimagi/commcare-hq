from unittest.mock import patch

from django.test import SimpleTestCase

from ...formplayer_api.exceptions import FormplayerAPIException
from ...formplayer_api.form_validation import FormValidationResult
from ..exceptions import (
    DangerousXmlException,
    XFormValidationError,
    XFormValidationFailed,
)
from ..xform import parse_xml, validate_xform


class ParseXMLTests(SimpleTestCase):
    def test_parses_normal_xml(self):
        xml = '''
        <html>
            <head>
                <title>Survery</title>
            </head>
        </html>
        '''.strip()
        parse_xml(xml)

    def test_parses_entity_only_in_dtd(self):
        xml = '''
        <!DOCTYPE foo [<!ENTITY example SYSTEM 'file://etc/hosts'>]>
        <html>
            <head>
                <title>Survery: example</title>
            </head>
        </html>
        '''.strip()
        parse_xml(xml)

    def test_throws_exception_with_entity_reference(self):
        xml = '''
        <!DOCTYPE foo [<!ENTITY example SYSTEM 'file://etc/hosts'>]>
        <html>
            <head>
                <title>Survery: &example;</title>
            </head>
        </html>
        '''.strip()

        with self.assertRaises(DangerousXmlException):
            parse_xml(xml)


@patch('corehq.apps.app_manager.xform.formplayer_api.validate_form')
class ValidateXFormTests(SimpleTestCase):
    """
    Bare bones test since the actual validation logic lives in formplayer
    """

    def test_validation_failed_exception_raised(self, mock_validate_form):
        xml = '''
        <html>
            <head>
                <title>Survey</title>
            </head>
        </html>
        '''.strip()

        mock_validate_form.side_effect = FormplayerAPIException

        with self.assertRaises(XFormValidationFailed):
            validate_xform(xml)

    def test_validation_error_exception_raised(self, mock_validate_form):
        xml = '''
        <html>
            <head>
                <title>Survey</title>
            </head>
        </html>
        '''.strip()

        validation_result = FormValidationResult(
            problems=[],
            success=False,
            fatal_error=None,
        )
        mock_validate_form.return_value = validation_result

        with self.assertRaises(XFormValidationError):
            validate_xform(xml)

    def test_successful(self, mock_validate_form):
        xml = '''
        <html>
            <head>
                <title>Survey</title>
            </head>
        </html>
        '''.strip()

        validation_result = FormValidationResult(
            problems=[],
            success=True,
            fatal_error=None,
        )
        mock_validate_form.return_value = validation_result
        try:
            validate_xform(xml)
        except XFormValidationFailed as e:
            self.fail(f"validate_xform raised {e} unexpectedly")
