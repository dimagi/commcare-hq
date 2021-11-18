from django.test import SimpleTestCase

from ..xform import parse_xml
from ..exceptions import DangerousXmlException


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
