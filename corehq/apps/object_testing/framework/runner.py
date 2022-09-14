import difflib
import json

from corehq.apps.object_testing.framework.exceptions import ObjectTestAssertionError
from corehq.apps.object_testing.framework.forms import RawJSONForm
from corehq.apps.userreports.models import UCRExpression
from corehq.apps.userreports.specs import EvaluationContext, FactoryContext


class BaseTestRunner:
    form_class = None

    def __init__(self, object_under_test, test_context, expected):
        self.object_under_test = object_under_test
        self.test_context = test_context
        self.raw_expected = expected

    @property
    def expected(self):
        form = self.form_class(self.raw_expected)
        if form.is_valid():
            return self.get_expected_from_cleaned_data(form.cleaned_data)
        else:
            raise Exception(form.errors)

    def get_expected_from_cleaned_data(self, cleaned_data):
        return cleaned_data["raw_json"]

    def assertExpectation(self, result):
        if result != self.expected:
            raise ObjectTestAssertionError(self.get_failure_message(result, self.expected))
        return True

    def get_failure_message(self, actual, expected):
        expected_norm = json.dumps(expected, indent=2)
        actual_norm = json.dumps(actual, indent=2)
        message = "{} mismatch\n\n".format("JSON")
        diff = difflib.unified_diff(
            expected_norm.splitlines(keepends=True),
            actual_norm.splitlines(keepends=True),
            fromfile='want.{}'.format("json"),
            tofile='got.{}'.format("json")
        )
        for line in diff:
            message += line
        return message


class UCRExpressionTestRunner(BaseTestRunner):
    form_class = RawJSONForm

    def run(self):
        eval_context = EvaluationContext(self.test_context)
        definition = self.object_under_test.wrapped_definition(FactoryContext())
        result = definition(self.test_context, eval_context)
        self.assertExpectation(result)
        return True


class TestRunnerFactory:
    mapping = {
        UCRExpression: UCRExpressionTestRunner
    }

    @classmethod
    def get_runner(cls, object_under_test):
        return cls.mapping[object_under_test.__class__]
