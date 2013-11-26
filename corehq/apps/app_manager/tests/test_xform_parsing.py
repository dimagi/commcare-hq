import os
from django.test import TestCase
from corehq.apps.app_manager.xform import XForm, XFormError

class XFormParsingTest(TestCase):
    def setUp(self):
        self.xforms = {}
        for filename in ("label_form.xml", "itext_form.xml"):
            file_path = os.path.join(os.path.dirname(__file__), "data", filename)
            with open(file_path) as f:
                self.xforms[filename] = XForm(f.read())
            self.xforms[filename].validate()

    def test_properties(self):
        for _,xform in self.xforms.items():
            xform.data_node
            xform.model_node
            xform.instance_node
            xform.case_node
            try:
                xform.itext_node
            except XFormError as e:
                self.assertEqual(str(e), "Can't find <itext>")

    def test_localize(self):
        try:
            self.assertEqual(self.xforms["label_form.xml"].localize(id="pork", lang="kosher"), None)
            self.fail()
        except XFormError as e:
            self.assertEqual(str(e), "Can't find <itext>")
        self.assertEqual(self.xforms["itext_form.xml"].localize(id="pork", lang="kosher"), None)
        self.assertEqual(self.xforms["itext_form.xml"].localize(id="question1", lang="pt"), "P1")
    