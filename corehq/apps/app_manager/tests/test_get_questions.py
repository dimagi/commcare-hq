import os

from django.test import TestCase

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.app_manager.models import Application, APP_V2

class GetFormQuestionsTest(TestCase):
    domain = 'test-domain'

    def setUp(self):
        def read(filename):
            path = os.path.join(os.path.dirname(__file__), "data", filename)
            with open(path) as f:
                return f.read()

        create_domain(self.domain)

        self.app = app = Application.new_app(
                self.domain, "Test", application_version=APP_V2)
        module = app.new_module("Module", 'en')
        module = app.get_module(0)
        module.case_type = 'test'

        form = app.new_form(module.id, name="Form", lang='en',
                attachment=read('case_in_form.xml'))

        self.form_unique_id = form.unique_id
        app.save()

    def test_get_questions(self):
        form = self.app.get_form(self.form_unique_id)
        questions = form.wrapped_xform().get_questions(['en', 'es'])
        
        self.assertEqual(questions, [
            {
                'tag': 'input',
                'repeat': '',
                'value': '/data/question1',
                'label': 'label en ____ label en'
            },
            {
                'tag': 'input',
                'repeat': '',
                'value': '/data/question2',
                'label': 'label en ____ label en'
            },
            {
                'tag': 'input',
                'repeat': '',
                'value': '/data/question3',
                'label': 'no references here!'
            },
            {
                'tag': 'input',
                'repeat': '/data/question15',
                'value': '/data/question15/question16',
                'label': None
            },
            {
                'tag': 'select1',
                'repeat': '/data/question15',
                'options': [
                    {'value': 'item22',
                     'label': None}
                ],
                'value': '/data/question15/question21',
                'label': None
            },
            {
                'tag': 'input',
                'repeat': '/data/question15',
                'value': '/data/question15/question25',
                'label': None
            },
            {
                'tag': 'input',
                'repeat': '',
                'value': '/data/thing',
                'label': None
            },
            {
                'tag': 'hidden',
                'repeat': '',
                'value': '/data/datanode',
                'label': '/data/datanode'
            },
        ])


        
