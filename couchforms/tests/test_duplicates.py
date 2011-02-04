import os
from django.test import TestCase
from couchforms.util import post_xform_to_couch

class DuplicateFormTest(TestCase):
    
    def testBasicDuplicate(self):
        file_path = os.path.join(os.path.dirname(__file__), "data", "duplicate.xml")
        
        with open(file_path, "rb") as f:
            xml_data = f.read()
        
        doc = post_xform_to_couch(xml_data)
        self.assertEqual("7H46J37FGH3", doc.get_id)
        self.assertEqual("XFormInstance", doc.doc_type)
        doc = post_xform_to_couch(xml_data)
        self.assertNotEqual("7H46J37FGH3", doc.get_id)
        self.assertEqual("XFormDuplicate", doc.doc_type)
        