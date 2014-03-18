from django.test import TestCase
from corehq.apps.app_manager.tests.util import TestFileMixin
from corehq.apps.app_manager.xform import XForm, XFormError

class XFormParsingTest(TestCase, TestFileMixin):
    file_path = ('data',)

    def setUp(self):
        self.xforms = {}
        for filename in ("label_form", "itext_form"):
            self.xforms[filename] = XForm(self.get_xml(filename))
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
            self.assertEqual(self.xforms["label_form"].localize(id="pork", lang="kosher"), None)
            self.fail()
        except XFormError as e:
            self.assertEqual(str(e), "Can't find <itext>")
        self.assertEqual(self.xforms["itext_form"].localize(id="pork", lang="kosher"), None)
        self.assertEqual(self.xforms["itext_form"].localize(id="question1", lang="pt"), "P1")

    def test_normalize_itext(self):
        original = self.xforms['itext_form']
        original.normalize_itext()
        self.assertXmlEqual(original.render(), self.get_xml('itext_form_normalized'))
