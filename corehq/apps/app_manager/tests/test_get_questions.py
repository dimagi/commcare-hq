from __future__ import absolute_import
from __future__ import unicode_literals
import os
import uuid

from django.template.loader import render_to_string
from django.test.testcases import SimpleTestCase

from corehq.util.test_utils import TestFileMixin
from corehq.apps.app_manager.models import Application, Module

QUESTIONS = [
    {
        'tag': 'input',
        'repeat': None,
        'group': None,
        'value': '/data/question1',
        'hashtagValue': '#form/question1',
        'label': 'label en ____ label en',
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
    },
    {
        'tag': 'input',
        'repeat': None,
        'group': None,
        'value': '/data/question2',
        'hashtagValue': '#form/question2',
        'label': 'label en ____ label en',
        'translations': {'en': 'label en ____ label en'},
        'type': 'Text',
        'required': False,
        'relevant': None,
        'constraint': None,
        'comment': "This is a comment",
        'setvalue': None,
    },
    {
        'tag': 'input',
        'repeat': None,
        'group': None,
        'value': '/data/question3',
        'hashtagValue': '#form/question3',
        'label': 'no references here!',
        'translations': {'en': 'no references here!'},
        'type': 'Text',
        'required': False,
        'relevant': None,
        'constraint': None,
        'comment': None,
        'setvalue': None,
    },
    {
        'tag': 'trigger',
        'repeat': None,
        'group': None,
        'value': '/data/hi',
        'hashtagValue': '#form/hi',
        'label': 'woo',
        'translations': {'en': 'woo'},
        'type': 'Trigger',
        'required': False,
        'relevant': None,
        'constraint': None,
        'comment': None,
        'setvalue': None,
    },
    {
        'tag': 'input',
        'repeat': '/data/question15',
        'group': '/data/question15',
        'value': '/data/question15/question16',
        'hashtagValue': '#form/question15/question16',
        'label': None,
        'translations': {},
        'type': 'Text',
        'required': False,
        'relevant': None,
        'constraint': '1',
        'comment': None,
        'setvalue': None,
    },
    {
        'tag': 'select1',
        'repeat': '/data/question15',
        'group': '/data/question15',
        'options': [
            {
                'value': 'item22',
                'label': None,
                'translations': {},
            }
        ],
        'value': '/data/question15/question21',
        'hashtagValue': '#form/question15/question21',
        'label': None,
        'translations': {},
        'type': 'Select',
        'required': False,
        'relevant': None,
        'constraint': None,
        'comment': None,
        'setvalue': None,
    },
    {
        'tag': 'input',
        'repeat': '/data/question15',
        'group': '/data/question15',
        'value': '/data/question15/question25',
        'hashtagValue': '#form/question15/question25',
        'label': None,
        'translations': {},
        'type': 'Int',
        'required': False,
        'relevant': None,
        'constraint': None,
        'comment': None,
        'setvalue': None,
    },
    {
        'tag': 'input',
        'repeat': None,
        'group': None,
        'value': '/data/thing',
        'hashtagValue': '#form/thing',
        'label': None,
        'translations': {},
        'type': 'Text',
        'required': False,
        'relevant': None,
        'constraint': None,
        'comment': None,
        'setvalue': None,
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
            attachment=self.get_xml('case_in_form')
        )

        form_with_repeats = self.app.new_form(
            module.id,
            name="Form with repeats",
            lang='en',
            attachment=self.get_xml('form_with_repeats')
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

        repeat_name_count = filter(
            lambda question: question['value'] == '/data/repeat_name_count',
            questions,
        )[0]
        self.assertIsNone(repeat_name_count['repeat'])

        repeat_question = filter(
            lambda question: question['value'] == '/data/repeat_name/question5',
            questions,
        )[0]
        self.assertEqual(repeat_question['repeat'], '/data/repeat_name')

    def test_blank_form(self):
        blank_form = render_to_string("app_manager/blank_form.xml", context={
            'xmlns': str(uuid.uuid4()).upper()
        })
        form = self.app.new_form(self.app.get_module(0).id, 'blank', 'en')
        form.source = blank_form

        questions = form.get_questions(['en'])
        self.assertEqual([], questions)
