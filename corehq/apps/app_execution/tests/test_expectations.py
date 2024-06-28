from django.test import SimpleTestCase
from testil import eq

from .utils import assert_json_dict_equal
from ..data_model import AppWorkflow
from ..data_model import expectations


class ExpectationModelTest(SimpleTestCase):

    def test_workflow_has_all_step_types(self):
        all_steps = _get_workflow().steps
        types_ = {step.type for step in all_steps}
        missing = expectations.TYPE_MAP.keys() - types_
        if missing:
            raise AssertionError(f"Missing expectation types: {missing}")

    def test_to_json(self):
        assert_json_dict_equal(_get_workflow().__jsonattrs_to_json__(), _get_workflow_json())

    def test_from_json(self):
        workflow = AppWorkflow.__jsonattrs_from_json__(_get_workflow_json())
        eq(workflow, _get_workflow())


def _get_workflow():
    return AppWorkflow(steps=[
        expectations.XpathExpectation(xpath="instance('commcaresession')/session/data/case/@case_id = '123'"),
        expectations.CasePresent(xpath_filter="@case_id = '123'"),
        expectations.CaseAbsent(xpath_filter="@case_id = '345'"),
        expectations.QuestionValue(question_path="/data/question1", value="123"),
    ])


def _get_workflow_json():
    return {
        "steps": [
            {"type": "expect:xpath", "xpath": "instance('commcaresession')/session/data/case/@case_id = '123'"},
            {"type": "expect:case_present", "xpath_filter": "@case_id = '123'"},
            {"type": "expect:case_absent", "xpath_filter": "@case_id = '345'"},
            {"type": "expect:question_value", "question_path": "/data/question1", "value": "123"},
        ]
    }
