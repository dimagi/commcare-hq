import os

from django.test import SimpleTestCase

from corehq.apps.app_execution.data_model import steps
from corehq.apps.app_execution.har_parser import HarParser
from corehq.util.test_utils import TestFileMixin


class TestHarExtraction(SimpleTestCase, TestFileMixin):
    file_path = ('data',)
    root = os.path.dirname(__file__)

    def test_extraction_reg_form(self):
        har_data = self.get_json("reg_form")
        config = HarParser().parse(har_data)
        self.assertEqual(config.domain, "demo_domain")
        self.assertEqual(config.app_id, "demo_app_id")
        self.assertEqual(config.workflow.steps, get_reg_form_steps())

    def test_extraction_case_list(self):
        har_data = self.get_json("case_list")
        config = HarParser().parse(har_data)
        self.assertEqual(config.domain, "demo_domain")
        self.assertEqual(config.app_id, "demo_app_id")
        self.assertEqual(config.workflow.steps, get_case_list_steps())

    def test_extraction_combined(self):
        reg_form_har_data = self.get_json("reg_form")
        case_list_har_data = self.get_json("case_list")
        combined = {
            'log': {
                'entries': reg_form_har_data['log']['entries'] + case_list_har_data['log']['entries']
            }
        }
        config = HarParser().parse(combined)
        self.assertEqual(config.domain, "demo_domain")
        self.assertEqual(config.app_id, "demo_app_id")
        self.assertEqual(config.workflow.steps, get_reg_form_steps() + get_case_list_steps())

    def test_split_screen_case_search_select(self):
        har = self.get_json("split_case_search_select")
        config = HarParser().parse(har)
        self.assertEqual(config.workflow.steps, [
            steps.CommandStep(value='Pending Cases'),
            steps.EntitySelectStep(value='0da3e5c6-f069-49be-aab3-53f2b9b7ebd0')
        ])

    def test_split_screen_case_search_search(self):
        har = self.get_json("split_case_search_search")
        config = HarParser().parse(har)
        self.assertEqual(config.workflow.steps, [
            steps.CommandStep(value='Pending Cases'),
            steps.QueryInputValidationStep(inputs={'name': 'stale1'}),
            steps.QueryStep(inputs={'name': 'stale1'}),
            steps.EntitySelectStep(value='0da3e5c6-f069-49be-aab3-53f2b9b7ebd0'),
        ])

    def test_search_again(self):
        har = self.get_json("search_again")
        config = HarParser().parse(har)
        self.assertEqual(config.workflow.steps, [
            steps.CommandStep(value='Include Related Cases'),
            steps.ClearQueryStep(),
            steps.QueryInputValidationStep(inputs={'first_name': 'Lucca'}),
            steps.QueryInputValidationStep(inputs={'first_name': 'Lucca', 'last_name': 'Mcpherson'}),
            steps.QueryStep(inputs={'first_name': 'Lucca', 'last_name': 'Mcpherson'}),
            steps.EntitySelectStep(value='18e434037dae4d87b98e77687a2aeff4'),
        ])

    def test_case_list_action(self):
        har = self.get_json("case_list_action")
        config = HarParser().parse(har)
        self.assertEqual(config.workflow.steps, [
            steps.CommandStep(value='Baby Log'),
            steps.CommandIdStep(value='action 0')
        ])


def get_reg_form_steps():
    return [
        steps.CommandStep(value='Register'),
        steps.CommandStep(value='Register cat'),
        steps.FormStep(children=[
            steps.AnswerQuestionIdStep(question_id='name', value='fluffy'),
            steps.AnswerQuestionIdStep(question_id='date', value='2024-05-14'),
            steps.SubmitFormStep()
        ])
    ]


def get_case_list_steps():
    return [
        steps.CommandStep(value='Register'),
        steps.CommandStep(value='Cat sighting'),
        steps.EntitySelectStep(value='7a6d6f96-9bd4-41c0-8e52-e499497c4991'),
        steps.FormStep(children=[steps.SubmitFormStep()])
    ]
