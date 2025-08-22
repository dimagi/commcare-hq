from unittest.mock import patch
from lxml import etree

from django.test import SimpleTestCase

from ...formplayer_api.exceptions import FormplayerAPIException
from ...formplayer_api.form_validation import FormValidationResult
from ..exceptions import (
    DangerousXmlException,
    XFormValidationError,
    XFormValidationFailed,
)
from corehq.apps.app_manager.models import Form, FormActions
from ..xform import parse_xml, validate_xform, XForm


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


class XForm_CreateCaseMappingsTests(SimpleTestCase):
    def test_creates_mappings(self):
        actions = FormActions({
            'update_case': {
                'update': {
                    'one': {'question_path': 'q1'},
                    'two': {'question_path': 'q2'}
                }
            }
        })

        form = Form(actions=actions)

        xform = XForm('')
        tree = xform.create_case_mappings(form)
        rendered_tree = etree.tostring(tree, encoding='unicode', pretty_print=True).strip()

        assert rendered_tree == """
<case_mappings>
  <mapping property="one">
    <question question_path="q1" update_mode="always"/>
  </mapping>
  <mapping property="two">
    <question question_path="q2" update_mode="always"/>
  </mapping>
</case_mappings>
""".strip()

    def test_creates_open_case_mappings(self):
        actions = FormActions({
            'open_case': {
                'name_update': {'question_path': 'name'}
            }
        })

        form = Form(actions=actions)

        xform = XForm('')
        tree = xform.create_case_mappings(form)
        rendered_tree = etree.tostring(tree, encoding='unicode', pretty_print=True).strip()

        assert rendered_tree == """
<case_mappings>
  <mapping property="name">
    <question question_path="name" update_mode="always"/>
  </mapping>
</case_mappings>
""".strip()

    def test_uses_name_from_open_case(self):
        actions = FormActions({
            'open_case': {
                'name_update': {'question_path': 'open_case_name'}
            },
            'update_case': {
                'update': {
                    'name': {'question_path': 'update_case_name'}
                }
            }
        })

        form = Form(actions=actions)

        xform = XForm('')
        tree = xform.create_case_mappings(form)
        rendered_tree = etree.tounicode(tree, pretty_print=True).strip()

        assert rendered_tree == """
<case_mappings>
  <mapping property="name">
    <question question_path="open_case_name" update_mode="always"/>
  </mapping>
</case_mappings>
""".strip()


class XForm_AddCaseMappingsTests(SimpleTestCase):
    def test_adds_case_mappings(self):
        actions = FormActions({
            'update_case': {
                'update': {
                    'one': {'question_path': 'q1'}
                }
            }
        })
        form = Form(actions=actions)
        xform = self._create_minimal_xform()

        xform.add_case_mappings(form)

        assert xform.find('case_mappings') is not None

    def test_handles_no_mappings(self):
        actions = FormActions()
        form = Form(actions=actions)
        xform = self._create_minimal_xform()

        xform.add_case_mappings(form)

        mappings_node = xform.find('case_mappings')
        assert len(mappings_node) == 0

    def test_does_not_create_duplicate_mapping_nodes(self):
        actions = FormActions({
            'update_case': {
                'update': {
                    'one': {'question_path': 'q1'}
                }
            }
        })
        form = Form(actions=actions)
        xform = self._create_minimal_xform()

        xform.add_case_mappings(form)
        xform.add_case_mappings(form)

        case_mapping_nodes = xform.findall('case_mappings')
        assert len(case_mapping_nodes) == 1

    def _create_minimal_xform(self):
        return XForm('''
<html xmlns="http://www.w3.org/2002/xforms" xmlns:h="http://www.w3.org/1999/xhtml">
    <h:head>
        <model>
            <instance>
                <data></data>
            </instance>
        </model>
    </h:head>
</html>
''')
