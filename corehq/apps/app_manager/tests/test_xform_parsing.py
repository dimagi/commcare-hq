# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import SimpleTestCase
from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.apps.app_manager.xform import XForm, XFormException, ItextValue, \
    WrappedNode, validate_xform


class XFormParsingTest(SimpleTestCase, TestXmlMixin):
    file_path = ('data',)

    def setUp(self):
        self.xforms = {}
        for filename in ("label_form", "itext_form"):
            xml = self.get_xml(filename)
            self.xforms[filename] = XForm(xml)

    def test_properties(self):
        for _, xform in self.xforms.items():
            xform.data_node
            xform.model_node
            xform.instance_node
            xform.case_node
            try:
                xform.itext_node
            except XFormException as e:
                self.assertEqual(str(e), "Can't find <itext>")

    def test_localize(self):
        try:
            self.assertEqual(self.xforms["label_form"].localize(id="pork", lang="kosher"), None)
            self.fail()
        except XFormException as e:
            self.assertEqual(str(e), "Can't find <itext>")
        self.assertEqual(self.xforms["itext_form"].localize(id="pork", lang="kosher"), None)
        self.assertEqual(self.xforms["itext_form"].localize(id="question1", lang="pt"), "P1")
        self.assertEqual(self.xforms["itext_form"].localize(id="question1", lang="en"), "Q1")
        self.assertEqual(self.xforms["itext_form"].localize(id="question1"), "Q1")

    def test_normalize_itext(self):
        original = self.xforms['itext_form']
        original.normalize_itext()
        self.assertXmlEqual(original.render(), self.get_xml('itext_form_normalized'))


class ItextValueTest(SimpleTestCase):

    def _test(self, escaped_itext, expected):
        itext_value = ItextValue.from_node(
            WrappedNode(
                '<value xmlns="http://www.w3.org/2002/xforms">%s</value>' % (
                    escaped_itext
                )
            )
        )
        self.assertEqual(itext_value, expected)

    def test_simple(self):
        self._test('This is a test', 'This is a test')

    def test_output_ref_middle(self):
        self._test('Test <output ref="/data/question1"/> test',
                   'Test ____ test')

    def test_output_ref_start(self):
        self._test('<output ref="/data/question1"/> Test test',
                   '____ Test test')

    def test_output_ref_end(self):
        self._test('Test test <output ref="/data/question1"/>',
                   'Test test ____')

    def test_output_value_middle(self):
        """Test whether @value works as well as @ref"""
        self._test('Test <output value="/data/question1"/> test',
                   'Test ____ test')

    def test_whitespace(self):
        self._test(' Test test  <output ref="/data/question1"/> ',
                   ' Test test  ____ ')
