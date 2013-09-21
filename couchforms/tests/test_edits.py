import os
from django.test import TestCase
from couchforms.models import XFormDeprecated
from couchforms.util import post_xform_to_couch

class EditFormTest(TestCase):
    
    def setUp(self):
        for form in XFormDeprecated.view('couchforms/edits', include_docs=True).all():
            form.delete()
            
    def testBasicEdit(self):
        first_file = os.path.join(os.path.dirname(__file__), "data", "duplicate.xml")
        edit_file = os.path.join(os.path.dirname(__file__), "data", "edit.xml")

        with open(first_file, "rb") as f:
            xml_data1 = f.read()
        with open(edit_file, "rb") as f:
            xml_data2 = f.read()

        docs = []

        doc = post_xform_to_couch(xml_data1)
        self.assertEqual("7H46J37FGH3", doc.get_id)
        self.assertEqual("XFormInstance", doc.doc_type)
        self.assertEqual("", doc.form['vitals']['height'])
        self.assertEqual("other", doc.form['assessment']['categories'])

        doc = post_xform_to_couch(xml_data2)
        self.assertEqual("7H46J37FGH3", doc.get_id)
        self.assertEqual("XFormInstance", doc.doc_type)
        self.assertEqual("100", doc.form['vitals']['height'])
        self.assertEqual("Edited Baby!", doc.form['assessment']['categories'])

        docs.append(doc)

        doc = XFormDeprecated.view('couchforms/edits', include_docs=True).first()
        self.assertEqual("7H46J37FGH3", doc.orig_id)
        self.assertNotEqual("7H46J37FGH3", doc.get_id)
        self.assertEqual(XFormDeprecated.__name__, doc.doc_type)
        self.assertEqual("", doc.form['vitals']['height'])
        self.assertEqual("other", doc.form['assessment']['categories'])

        for doc in docs:
            doc.delete()
