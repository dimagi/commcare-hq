import os
import unittest
from xml.etree.ElementTree import Element

from django.template.loader import render_to_string
from django.test.testcases import SimpleTestCase

from corehq.apps.app_manager.models import Application, Module
from corehq.apps.app_manager.util import generate_xmlns
from corehq.apps.app_manager.xform import XForm
from corehq.util.test_utils import TestFileMixin

QUESTIONS = [
    {
        'tag': 'input',
        'repeat': None,
        'group': None,
        'constraintMsg_ref': 'question1-constraintMsg',
        'value': '/data/question1',
        'hashtagValue': '#form/question1',
        'label': 'label en ____ label en',
        'label_ref': 'question1-label',
        'translations': {
            'en': 'label en ____ label en',
            'es': 'label es ____\n____\n____',
        },
        'type': 'Text',
        'required': False,
        'relevant': ("instance('casedb')/casedb/case[@case_id=instance('casedb')/casedb/case["
                     "@case_id=instance('commcaresession')/session/data/case_id]/index/parent"
                     "]/parent_property_1 + 1 + "
                     "instance('casedb')/casedb/case[@case_id=instance('casedb')/casedb/case["
                     "@case_id=instance('commcaresession')/session/data/case_id]/index/parent"
                     "]/parent_property_1"),
        'constraint': "1 + instance('casedb')/casedb/case[@case_id=instance('commcaresession')/session/data/case_id]/child_property_1",
        'comment': None,
        'setvalue': None,
        'is_group': False,
    },
    {
        'tag': 'input',
        'repeat': None,
        'group': None,
        'value': '/data/question2',
        'hashtagValue': '#form/question2',
        'label': 'label en ____ label en',
        'label_ref': 'question2-label',
        'translations': {'en': 'label en ____ label en'},
        'type': 'Text',
        'required': False,
        'relevant': None,
        'constraint': None,
        'comment': "This is a comment",
        'setvalue': None,
        'is_group': False,
    },
    {
        'tag': 'input',
        'repeat': None,
        'group': None,
        'value': '/data/question3',
        'hashtagValue': '#form/question3',
        'label': 'no references here!',
        'label_ref': 'question3-label',
        'translations': {'en': 'no references here!'},
        'type': 'Text',
        'required': False,
        'relevant': None,
        'constraint': None,
        'comment': None,
        'setvalue': None,
        'is_group': False,
    },
    {
        'tag': 'trigger',
        'repeat': None,
        'group': None,
        'value': '/data/hi',
        'hashtagValue': '#form/hi',
        'label': 'woo',
        'label_ref': 'hi-label',
        'translations': {'en': 'woo'},
        'type': 'Trigger',
        'required': False,
        'relevant': None,
        'constraint': None,
        'comment': None,
        'setvalue': None,
        'is_group': False,
    },
    {
        'tag': 'input',
        'repeat': '/data/question15',
        'group': '/data/question15',
        'value': '/data/question15/question16',
        'hashtagValue': '#form/question15/question16',
        'label': None,
        'label_ref': 'question16-label',
        'translations': {},
        'type': 'Text',
        'required': False,
        'relevant': None,
        'constraint': '1',
        'comment': None,
        'setvalue': None,
        'is_group': False,
    },
    {
        'tag': 'select1',
        'repeat': '/data/question15',
        'group': '/data/question15',
        'options': [
            {
                'value': 'item22',
                'label': None,
                'label_ref': 'question21-item22-label',
                'translations': {},
            }
        ],
        'value': '/data/question15/question21',
        'hashtagValue': '#form/question15/question21',
        'label': None,
        'label_ref': 'question21-label',
        'translations': {},
        'type': 'Select',
        'required': False,
        'relevant': None,
        'constraint': None,
        'comment': None,
        'setvalue': None,
        'is_group': False,
    },
    {
        'tag': 'input',
        'repeat': '/data/question15',
        'group': '/data/question15',
        'value': '/data/question15/question25',
        'hashtagValue': '#form/question15/question25',
        'label': None,
        'label_ref': 'question25-label',
        'translations': {},
        'type': 'Int',
        'required': False,
        'relevant': None,
        'constraint': None,
        'comment': None,
        'setvalue': None,
        'is_group': False,
    },
    {
        'tag': 'input',
        'repeat': None,
        'group': None,
        'value': '/data/thing',
        'hashtagValue': '#form/thing',
        'label': None,
        'label_ref': 'thing-label',
        'translations': {},
        'type': 'Text',
        'required': False,
        'relevant': None,
        'constraint': None,
        'comment': None,
        'setvalue': None,
        'is_group': False,
    },
    {
        'tag': 'hidden',
        'repeat': None,
        'group': None,
        'value': '/data/datanode',
        'hashtagValue': '#form/datanode',
        'label': '#form/datanode',
        'translations': {},
        'type': 'DataBindOnly',
        'relevant': None,
        'calculate': None,
        'constraint': None,
        'comment': None,
        'setvalue': None,
    },
]


class GetFormQuestionsTest(SimpleTestCase, TestFileMixin):
    domain = 'test-domain'

    file_path = ('data',)
    root = os.path.dirname(__file__)

    maxDiff = None

    def setUp(self):
        self.app = Application.new_app(self.domain, "Test")
        self.app.add_module(Module.new_module("Module", 'en'))
        module = self.app.get_module(0)
        module.case_type = 'test'

        form = self.app.new_form(
            module.id,
            name="Form",
            lang='en',
            attachment=self.get_xml('case_in_form').decode('utf-8')
        )

        form_with_repeats = self.app.new_form(
            module.id,
            name="Form with repeats",
            lang='en',
            attachment=self.get_xml('form_with_repeats').decode('utf-8')
        )

        self.form_unique_id = form.unique_id
        self.form_with_repeats_unique_id = form_with_repeats.unique_id

    def test_get_questions(self):
        form = self.app.get_form(self.form_unique_id)
        questions = form.wrapped_xform().get_questions(['en', 'es'], include_translations=True)

        non_label_questions = [
            q for q in QUESTIONS if q['tag'] not in ('label', 'trigger')]

        self.assertEqual(questions, non_label_questions)

    def test_get_questions_with_triggers(self):
        form = self.app.get_form(self.form_unique_id)
        questions = form.wrapped_xform().get_questions(
            ['en', 'es'], include_triggers=True, include_translations=True)

        self.assertEqual(questions, QUESTIONS)

    def test_get_questions_with_repeats(self):
        """
        This test ensures that questions that start with the repeat group id
        do not get marked as repeats. For example:

            /data/repeat_name <-- repeat group path
            /data/repeat_name_count <-- question path

        Before /data/repeat_name_count would be tagged as a repeat incorrectly.
        See http://manage.dimagi.com/default.asp?234108 for context
        """
        form = self.app.get_form(self.form_with_repeats_unique_id)
        questions = form.wrapped_xform().get_questions(
            ['en'],
            include_groups=True,
        )

        repeat_name_count = list(filter(
            lambda question: question['value'] == '/data/repeat_name_count',
            questions,
        ))[0]
        self.assertIsNone(repeat_name_count['repeat'])

        repeat_question = list(filter(
            lambda question: question['value'] == '/data/repeat_name/question5',
            questions,
        ))[0]
        self.assertEqual(repeat_question['repeat'], '/data/repeat_name')

    def test_blank_form(self):
        blank_form = render_to_string("app_manager/blank_form.xml", context={
            'xmlns': generate_xmlns(),
        })
        form = self.app.new_form(self.app.get_module(0).id, 'blank', 'en')
        form.source = blank_form

        questions = form.get_questions(['en'])
        self.assertEqual([], questions)

    def test_save_to_case_in_groups(self):
        """Ensure that save to case questions have the correct group and repeat context
        when there are no other questions in that group

        """
        save_to_case_with_groups = self.app.new_form(
            self.app.get_module(0).id,
            name="Save to case in groups",
            lang='en',
            attachment=self.get_xml('save_to_case_in_groups').decode('utf-8')
        )
        questions = save_to_case_with_groups.get_questions(['en'], include_groups=True, include_triggers=True)
        group_question = [q for q in questions if q['value'] == '/data/a_group/save_to_case_in_group/case'][0]
        repeat_question = [q for q in questions if q['value'] == '/data/a_repeat/save_to_case_in_repeat/case'][0]

        self.assertEqual(group_question['group'], '/data/a_group')
        self.assertIsNone(group_question['repeat'])

        self.assertEqual(repeat_question['repeat'], '/data/a_repeat')
        self.assertEqual(repeat_question['group'], '/data/a_repeat')

    def test_fixture_references(self):
        form_with_fixtures = self.app.new_form(
            self.app.get_module(0).id,
            name="Form with Fixtures",
            lang='en',
            attachment=self.get_xml('form_with_fixtures').decode('utf-8')
        )
        questions = form_with_fixtures.get_questions(['en'], include_fixtures=True)
        self.assertEqual(questions[0], {
            "comment": None,
            "constraint": None,
            "data_source": {
                "instance_id": "country",
                "instance_ref": "jr://fixture/item-list:country",
                "nodeset": "instance('country')/country_list/country",
                "label_ref": "name",
                "value_ref": "id",
            },
            "group": None,
            "hashtagValue": "#form/lookup-table",
            "is_group": False,
            "label": "I'm a lookup table!",
            "label_ref": "lookup-table-label",
            "options": [],
            "relevant": None,
            "repeat": None,
            "required": False,
            "setvalue": None,
            "tag": "select1",
            "type": "Select",
            "value": "/data/lookup-table"
        })


class TestGetQuestionsExtended(unittest.TestCase):
    """
    Extended tests for the modified XForm.get_questions() method.
    These tests cover new functionality related to translations, fixtures,
    triggers, groups, and single-question retrieval.
    """
    # Added by GitHub Copilot using o1

    def _build_xml_root(self):
        """
        Helper method to build a sample XML structure for testing.
        Each child node includes attributes that simulate question data.
        """
        root = Element('root')

        # Simple text question
        question1 = Element('question')
        question1.set('type', 'text')
        question1.set('value', '/data/question1')
        question1.set('label', 'What is your name?')
        question1.set('label_en', 'What is your name?')
        question1.set('label_es', '¿Cuál es su nombre?')
        root.append(question1)

        # Trigger question
        trigger_q = Element('question')
        trigger_q.set('type', 'trigger')
        trigger_q.set('value', '/data/trigger_q')
        trigger_q.set('label', 'Trigger question')
        root.append(trigger_q)

        # Group question
        group_q = Element('question')
        group_q.set('type', 'group')
        group_q.set('value', '/data/group_q')
        group_q.set('label', 'Group heading')
        root.append(group_q)

        # Question referencing a fixture
        fixture_q = Element('question')
        fixture_q.set('type', 'text')
        fixture_q.set('value', '/data/fixture_q')
        fixture_q.set('label', 'Select a product')
        fixture_q.set('fixture', 'product_fixture')
        root.append(fixture_q)

        return root

    def test_get_questions_default_behavior(self):
        """
        Test that get_questions() returns all text-type questions by default
        and excludes triggers/groups unless specifically included.
        """
        xml_root = self._build_xml_root()
        xform = XForm(xml_root)
        questions = xform.get_questions()

        self.assertEqual(len(questions), 2)  # Only text-type questions by default
        self.assertEqual(questions[0]['label'], 'What is your name?')
        self.assertEqual(questions[0]['value'], '/data/question1')

    def test_get_questions_include_triggers(self):
        """
        Test that setting include_triggers=True includes trigger-type questions.
        """
        xml_root = self._build_xml_root()
        xform = XForm(xml_root)
        questions = xform.get_questions(include_triggers=True)

        # We expect to see the text questions + 1 trigger
        self.assertEqual(len(questions), 3)
        trigger_question = [q for q in questions if q['type'] == 'trigger']
        self.assertEqual(len(trigger_question), 1)

    def test_get_questions_include_groups(self):
        """
        Test that setting include_groups=True includes group-type questions.
        """
        xml_root = self._build_xml_root()
        xform = XForm(xml_root)
        questions = xform.get_questions(include_groups=True)

        # We expect to see the text questions + 1 group
        self.assertEqual(len(questions), 3)
        group_question = [q for q in questions if q['type'] == 'group']
        self.assertEqual(len(group_question), 1)

    def test_get_questions_with_translations(self):
        """
        Test that translations are returned when include_translations=True.
        """
        xml_root = self._build_xml_root()
        xform = XForm(xml_root)
        questions = xform.get_questions(include_translations=True, langs=['en', 'es'])

        # The first question should contain translations in English and Spanish
        self.assertIn('translations', questions[0])
        self.assertIn('en', questions[0]['translations'])
        self.assertIn('es', questions[0]['translations'])

    def test_get_questions_with_fixtures(self):
        """
        Test that fixture references are returned when include_fixtures=True.
        """
        xml_root = self._build_xml_root()
        xform = XForm(xml_root)
        questions = xform.get_questions(include_fixtures=True)

        # Find the question that has a fixture
        fixture_question = [q for q in questions if q['value'] == '/data/fixture_q']
        self.assertEqual(len(fixture_question), 1)
        self.assertIn('fixtures', fixture_question[0])
        self.assertEqual(fixture_question[0]['fixtures'], ['product_fixture'])

    def test_get_questions_only_first(self):
        """
        Test that only the first question is returned when only_first=True.
        """
        xml_root = self._build_xml_root()
        xform = XForm(xml_root)
        first_question = xform.get_questions(only_first=True)

        # Expect a single question (dict), not a list
        self.assertIsInstance(first_question, dict)
        self.assertEqual(first_question['value'], '/data/question1')
