import os
from django.test import TestCase
from corehq.apps.app_manager.xform import XForm

class XFormParsingTest(TestCase):
    def setUp(self):
        self.xforms = {}
        for filename in ("label_form.xml", "itext_form.xml"):
            file_path = os.path.join(os.path.dirname(__file__), "data", filename)
            with open(file_path) as f:
                self.xforms[filename] = XForm(f.read())

    def test_properties(self):
        for _,xform in self.xforms.items():
            xform.data_node
            xform.model_node
            xform.instance_node
            xform.itext_node
            xform.case_node

    def test_localize(self):
        for filename, xform in self.xforms.items():
            self.failUnlessEqual(xform.localize(id="pork", lang="kosher"), None)

        self.failUnlessEqual(self.xforms["itext_form.xml"].localize(id="question1", lang="pt"), "P1")
    