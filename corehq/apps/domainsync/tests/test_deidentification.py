from django.test import TestCase
from corehq.apps.hqadmin.dbaccessors import get_all_forms_in_all_domains
from couchforms.models import XFormInstance
from couchforms.tests.testutils import post_xform_to_couch
import os
import json
from dimagi.utils.couch.database import get_db
from ..config import DocumentTransform
from ..deidentification.forms import deidentify_form


class FormDeidentificationTestCase(TestCase):

    def setUp(self):

        for item in get_all_forms_in_all_domains():
            item.delete()

    def testCRSReg(self):
        file_path = os.path.join(os.path.dirname(__file__), "data", "crs_reg.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        
        self.instance = post_xform_to_couch(xml_data)
        
        transform = DocumentTransform(self.instance._doc, get_db())
        self.assertTrue("IDENTIFIER" in json.dumps(transform.doc))
        self.assertTrue("IDENTIFIER" in transform.attachments["form.xml"])
        
        deidentified = deidentify_form(transform)
        self.assertTrue("IDENTIFIER" not in json.dumps(deidentified.doc))
        self.assertTrue("IDENTIFIER" not in deidentified.attachments["form.xml"])
    
    def testCRSChecklist(self):
        file_path = os.path.join(os.path.dirname(__file__), "data", "crs_checklist.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        
        self.instance = post_xform_to_couch(xml_data)
        
        transform = DocumentTransform(self.instance._doc, get_db())
        self.assertTrue("IDENTIFIER" in json.dumps(transform.doc))
        self.assertTrue("IDENTIFIER" in transform.attachments["form.xml"])
        self.assertTrue("YESNO" in json.dumps(transform.doc))
        self.assertTrue("YESNO" in transform.attachments["form.xml"])
        
        deidentified = deidentify_form(transform)
        self.assertTrue("IDENTIFIER" not in json.dumps(deidentified.doc))
        self.assertTrue("IDENTIFIER" not in deidentified.attachments["form.xml"])
        self.assertTrue("YESNO" not in json.dumps(deidentified.doc))
        self.assertTrue("YESNO" not in deidentified.attachments["form.xml"])
