import os

from django.test import SimpleTestCase

from corehq.apps.app_manager.models import _parse_xml


class XMLParsingTest(SimpleTestCase):

    def testUnicodeError(self):
        """Tests a bug found in Unicode processing of a form"""
        file_path = os.path.join(os.path.dirname(__file__), "data", "unicode_error_form.xhtml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        try:
            _parse_xml(xml_data) # this should not raise an error
        except:    
            self.fail("Parsing normal string data shouldn't fail!")
        try:
            _parse_xml(xml_data.decode('utf-8'))
        except:    
            self.fail("Parsing unicode data shouldn't fail!")
