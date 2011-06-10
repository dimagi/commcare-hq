import os
from django.test import TestCase
from couchforms.models import XFormInstance
from couchforms.util import post_xform_to_couch

class DuplicateFormTest(TestCase):

    def setUp(self):
        try:
            XFormInstance.get_db().delete_doc("7H46J37FGH3")
        except:
            pass

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
        self.assertTrue("7H46J37FGH3" in doc.problem)

        dupe_id = doc.get_id


        XFormInstance.get_db().delete_doc("7H46J37FGH3")
        XFormInstance.get_db().delete_doc(dupe_id)
        