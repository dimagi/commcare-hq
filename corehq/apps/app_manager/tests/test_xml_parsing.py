import os

from django.test import SimpleTestCase

from corehq.apps.app_manager.xform import parse_xml

class XMLParsingTest(SimpleTestCase):

    def testUnicodeError(self):
        """Tests a bug found in Unicode processing of a form"""
        file_path = os.path.join(os.path.dirname(__file__), "data", "unicode_error_form.xhtml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        try:
            parse_xml(xml_data) # this should not raise an error
        except Exception:
            self.fail("Parsing normal string data shouldn't fail!")
        try:
            parse_xml(xml_data.decode('utf-8'))
        except Exception:
            self.fail("Parsing unicode data shouldn't fail!")
