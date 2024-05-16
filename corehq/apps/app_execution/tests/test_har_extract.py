import json
import os

from django.test import SimpleTestCase

from corehq.apps.app_execution import data_model
from corehq.apps.app_execution.har_parser import HarParser
from corehq.util.test_utils import TestFileMixin


class TestHarExtraction(SimpleTestCase, TestFileMixin):
    file_path = ('data',)
    root = os.path.dirname(__file__)

    def test_extraction_reg_form(self):
        har_data = json.loads(self.get_file("reg_form", "har"))
        config = HarParser().parse(har_data)
        self.assertEqual(config.domain, "demo_domain")
        self.assertEqual(config.app_id, "demo_app_id")
        self.assertEqual(config.workflow.steps, get_reg_form_steps())

    def test_extraction_case_list(self):
        har_data = json.loads(self.get_file("case_list", "har"))
        config = HarParser().parse(har_data)
        self.assertEqual(config.domain, "demo_domain")
        self.assertEqual(config.app_id, "demo_app_id")
        self.assertEqual(config.workflow.steps, get_case_list_steps())

    def test_extraction_combined(self):
        reg_form_har_data = json.loads(self.get_file("reg_form", "har"))
        case_list_har_data = json.loads(self.get_file("case_list", "har"))
        combined = {
            'log': {
                'entries': reg_form_har_data['log']['entries'] + case_list_har_data['log']['entries']
            }
        }
        config = HarParser().parse(combined)
        self.assertEqual(config.domain, "demo_domain")
        self.assertEqual(config.app_id, "demo_app_id")
        self.assertEqual(config.workflow.steps, get_reg_form_steps() + get_case_list_steps())


def get_reg_form_steps():
    return [
        data_model.CommandStep(value='Register'),
        data_model.CommandStep(value='Register cat'),
        data_model.FormStep(children=[
            data_model.AnswerQuestionStep(question_text='Name', question_id='name', value='fluffy'),
            data_model.AnswerQuestionStep(question_text='Date', question_id='date', value='2024-05-14'),
            data_model.SubmitFormStep()
        ])
    ]


def get_case_list_steps():
    return [
        data_model.CommandStep(value='Register'),
        data_model.CommandStep(value='Cat sighting'),
        data_model.EntitySelectStep(value='7a6d6f96-9bd4-41c0-8e52-e499497c4991'),
        data_model.FormStep(children=[data_model.SubmitFormStep()])
    ]
