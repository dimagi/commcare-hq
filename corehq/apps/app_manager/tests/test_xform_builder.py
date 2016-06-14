# coding: utf-8
from django.test import SimpleTestCase
import re
from corehq.apps.app_manager.tests import TestXmlMixin
from corehq.apps.app_manager.xform_builder import XFormBuilder


class XFormBuilderTests(SimpleTestCase, TestXmlMixin):
    file_path = ('data', 'xform_builder')

    def setUp(self):
        self.xform = XFormBuilder()

    def replace_xmlns(self, xml, xmlns):
        return re.sub(r'http://openrosa\.org/formdesigner/[\w-]{36}', xmlns, xml)

    def test_new_question_group(self):
        """
        XFormBuilder.new_question should be able to add a group
        """
        self.xform.new_question('personal', 'Personal Questions', data_type='group')
        self.xform.new_question('name', 'What is your name?', group='personal')
        self.assertXmlEqual(
            self.replace_xmlns(self.get_xml('group'), self.xform.xmlns),
            self.xform.tostring(pretty_print=True, encoding='utf-8', xml_declaration=True)
        )

    def test_new_question_repeat_group(self):
        num_names = self.xform.new_question('num_names', 'How many names do you have?', data_type='int')
        self.xform.new_question('personal', 'Personal Questions', data_type='repeatGroup',
                                repeat_count=num_names)
        self.xform.new_question('name', 'What is your <output value="ordinal(position(..) + 1)" /> name?',
                                group='personal', label_safe=True)
        # Yes, that was plug for an ordinal function. cf. UserVoice:
        # https://dimagi.uservoice.com/forums/176376-form-builder/suggestions/10610517--ordinal-function
        self.assertXmlEqual(
            self.replace_xmlns(self.get_xml('repeat_group'), self.xform.xmlns),
            self.xform.tostring(pretty_print=True, encoding='utf-8', xml_declaration=True)
        )

    def test_new_group_group(self):
        personal = self.xform.new_group('personal', 'Personal Questions')
        personal.new_question('name', 'What is your name?')
        self.assertXmlEqual(
            self.replace_xmlns(self.get_xml('group'), self.xform.xmlns),
            self.xform.tostring(pretty_print=True, encoding='utf-8', xml_declaration=True)
        )

    def test_new_group_repeat_group(self):
        num_names = self.xform.new_question('num_names', 'How many names do you have?', data_type='int')
        personal = self.xform.new_group('personal', 'Personal Questions', data_type='repeatGroup',
                                        repeat_count=num_names)
        personal.new_question('name', 'What is your <output value="ordinal(position(..) + 1)" /> name?',
                              label_safe=True)
        self.assertXmlEqual(
            self.replace_xmlns(self.get_xml('repeat_group'), self.xform.xmlns),
            self.xform.tostring(pretty_print=True, encoding='utf-8', xml_declaration=True)
        )

    def test_unicode(self):
        self.xform.new_question('name', u'သင့်နာမည်ဘယ်လိုခေါ်လဲ?')  # ("What is your name?" in Myanmar/Burmese)
        self.assertXmlEqual(
            self.replace_xmlns(self.get_xml('unicode'), self.xform.xmlns),
            self.xform.tostring(pretty_print=True, encoding='utf-8', xml_declaration=True)
        )

    def test_select_question(self):
        self.xform.new_question('fav_colors', 'What are your favorite colors?', data_type='select', choices={
            'r': 'Red',
            'o': 'Orange',
            'y': 'Yellow',
            'g': 'Green',
            'b': 'Blue',
            'i': 'Indigo',
            'v': 'Violet',
        })
        self.assertXmlEqual(
            self.replace_xmlns(self.get_xml('select_question'), self.xform.xmlns),
            self.xform.tostring(pretty_print=True, encoding='utf-8', xml_declaration=True)
        )

    def test_select1_question(self):
        self.xform.new_question('you_aint_been_blue', 'What kind of blue are you?', data_type='select1', choices={
            1: 'Blue',
            2: 'Indigo',
            3: 'Black',
        })
        self.assertXmlEqual(
            self.replace_xmlns(self.get_xml('select1_question'), self.xform.xmlns),
            self.xform.tostring(pretty_print=True, encoding='utf-8', xml_declaration=True)
        )

    def test_data_types(self):
        self.xform.new_question('name', 'Child name')
        self.xform.new_question('dob', 'Child date of birth', 'date')
        self.xform.new_question('with_mother', 'Does child live with mother?', 'boolean',
                                value='true')
        self.xform.new_question('height', 'Child height (cm)', 'int')
        self.xform.new_question('weight', 'Child weight (metric tonnes)', 'decimal')
        self.xform.new_question('time', 'Arrival time', 'time')
        self.xform.new_question('now', 'Current timestamp', 'dateTime')
        self.xform.new_question('mothers_name', None, None,  # Hidden values have no data type
                                calculate="concat('Jane', ' ', 'Smith')")
        self.assertXmlEqual(
            self.replace_xmlns(self.get_xml('data_types'), self.xform.xmlns),
            self.xform.tostring(pretty_print=True, encoding='utf-8', xml_declaration=True)
        )

    def test_xform_title(self):
        self.xform = XFormBuilder('Built by XFormBuilder')
        self.xform.new_question('name', 'What is your name?')
        group = self.xform.new_group('personal', 'Personal Questions')
        group.new_question('fav_color', u'Quelle est ta couleur préférée?',
                           choices={'r': 'Rot', 'g': u'Grün', 'b': 'Blau'})
        self.assertXmlEqual(
            self.replace_xmlns(self.get_xml('xform_title'), self.xform.xmlns),
            self.xform.tostring(pretty_print=True, encoding='utf-8', xml_declaration=True)
        )

    def test_question_params(self):
        self.xform = XFormBuilder('Built by XFormBuilder')
        params = {
            'constraint': ". != 'Ford Prefect'",
            'jr:constraintMsg': 'That name is not as inconspicuous as you think.'
        }
        self.xform.new_question('name', 'What is your name?', **params)
        self.assertXmlEqual(
            self.replace_xmlns(self.get_xml('question_params'), self.xform.xmlns),
            self.xform.tostring(pretty_print=True, encoding='utf-8', xml_declaration=True)
        )
