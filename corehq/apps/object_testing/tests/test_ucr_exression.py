from django.test import TestCase

from corehq.apps.object_testing.framework.exceptions import ObjectTestAssertionError
from corehq.apps.object_testing.framework.main import execute_object_test
from corehq.apps.object_testing.models import ObjectTest, ContextFactoryChoices
from corehq.apps.userreports.const import UCR_NAMED_EXPRESSION
from corehq.apps.userreports.models import UCRExpression


class TestUCRExpressionTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.object_under_test = UCRExpression(
            name='create_sport',
            domain='test',
            expression_type=UCR_NAMED_EXPRESSION,
            definition={
                'type': 'dict',
                'properties': {
                    'case_type': 'sport',
                    'case_name': {
                        'type': 'jsonpath',
                        'jsonpath': 'name',
                    },
                    'is_team_sport': {
                        'type': 'jsonpath',
                        'jsonpath': 'is_team_sport'
                    }
                }
            },
        )

    def test_simple_raw(self):
        test = ObjectTest(
            content_object=self.object_under_test,
            context_factory=ContextFactoryChoices.raw,
            input={'name': 'cricket', 'is_team_sport': True},
            expected={'case_type': 'sport', 'case_name': 'cricket', 'is_team_sport': True}
        )
        self.assertTrue(execute_object_test(test))

    def test_simple_raw_fail(self):
        test = ObjectTest(
            content_object=self.object_under_test,
            context_factory=ContextFactoryChoices.raw,
            input={'name': 'cricket', 'is_team_sport': True},
            expected={'case_type': 'sport', 'case_name': 'cricket'}
        )
        with self.assertRaises(ObjectTestAssertionError):
            execute_object_test(test)

    def test_simple_raw_expect_string(self):
        expression = UCRExpression(
            name='get_name',
            domain='test',
            expression_type=UCR_NAMED_EXPRESSION,
            definition={
                'type': 'jsonpath',
                'jsonpath': "name"
            },
        )
        test = ObjectTest(
            content_object=expression,
            context_factory=ContextFactoryChoices.raw,
            input={'name': 'cricket'},
            expected='cricket',
        )
        self.assertTrue(execute_object_test(test))
