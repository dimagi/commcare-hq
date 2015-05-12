import os

from django.test.testcases import SimpleTestCase

from corehq.apps.app_manager.models import Application, Module, APP_V2

QUESTIONS = [
    {
        'tag': 'input',
        'repeat': None,
        'group': None,
        'value': '/data/question1',
        'label': u'label en ____ label en',
        'translations': {
            'en': u'label en ____ label en',
            'es': u'label es ____\n____\n____',
        },
        'type': 'Text',
        'required': False,
        'relevant': ("instance('casedb')/casedb/case[@case_id=instance('casedb')/casedb/case["
                     "@case_id=instance('commcaresession')/session/data/case_id]/index/parent"
                     "]/parent_property_1 + 1 + "
                     "instance('casedb')/casedb/case[@case_id=instance('casedb')/casedb/case["
                     "@case_id=instance('commcaresession')/session/data/case_id]/index/parent"
                     "]/parent_property_1"),
    },
    {
        'tag': 'input',
        'repeat': None,
        'group': None,
        'value': '/data/question2',
        'label': u'label en ____ label en',
        'translations': {'en': u'label en ____ label en'},
        'type': 'Text',
        'required': False,
        'relevant': None,
    },
    {
        'tag': 'input',
        'repeat': None,
        'group': None,
        'value': '/data/question3',
        'label': u'no references here!',
        'translations': {'en': u'no references here!'},
        'type': 'Text',
        'required': False,
        'relevant': None,
    },
    {
        'tag': 'trigger',
        'repeat': None,
        'group': None,
        'value': '/data/hi',
        'label': 'woo',
        'translations': {'en': u'woo'},
        'type': 'Trigger',
        'required': False,
        'relevant': None,
    },
    {
        'tag': 'input',
        'repeat': '/data/question15',
        'group': '/data/question15',
        'value': '/data/question15/question16',
        'label': None,
        'translations': {},
        'type': 'Text',
        'required': False,
        'relevant': None,
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
        'label': None,
        'translations': {},
        'type': 'Select',
        'required': False,
        'relevant': None,
    },
    {
        'tag': 'input',
        'repeat': '/data/question15',
        'group': '/data/question15',
        'value': '/data/question15/question25',
        'label': None,
        'translations': {},
        'type': 'Int',
        'required': False,
        'relevant': None,
    },
    {
        'tag': 'input',
        'repeat': None,
        'group': None,
        'value': '/data/thing',
        'label': None,
        'translations': {},
        'type': 'Text',
        'required': False,
        'relevant': None,
    },
    {
        'tag': 'hidden',
        'repeat': None,
        'group': None,
        'value': '/data/datanode',
        'label': '/data/datanode',
        'translations': {},
        'type': 'DataBindOnly',
        'calculate': None
    },
]


class GetFormQuestionsTest(SimpleTestCase):
    domain = 'test-domain'

    maxDiff = None

    def setUp(self):
        def read(filename):
            path = os.path.join(os.path.dirname(__file__), "data", filename)
            with open(path) as f:
                return f.read()

        self.app = app = Application.new_app(
                self.domain, "Test", application_version=APP_V2)
        app.add_module(Module.new_module("Module", 'en'))
        module = app.get_module(0)
        module.case_type = 'test'

        form = app.new_form(module.id, name="Form", lang='en',
                attachment=read('case_in_form.xml'))

        self.form_unique_id = form.unique_id

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
