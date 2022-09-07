from django.core.exceptions import FieldError
from django.test import TestCase

from corehq.apps.userreports.const import UCR_NAMED_EXPRESSION
from corehq.apps.userreports.models import UCRExpression
from corehq.apps.userreports.specs import EvaluationContext
from corehq.motech.generic_inbound.models import ConfigurableAPI


class TestGenericInboundModels(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.expression = UCRExpression.objects.create(
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

        cls.api = ConfigurableAPI.objects.create(
            domain='test',
            transform_expression=cls.expression
        )

    def test_key_created(self):
        self.assertIsNotNone(self.api.key)
        self.assertTrue(len(self.api.key) > 0)

    def test_key_read_only(self):
        self.assertIsNotNone(self.api.key)
        self.api.key = 'new key'
        with self.assertRaisesRegex(FieldError, "'key' can not be changed"):
            self.api.save()

    def test_transform(self):
        body = {'name': 'cricket', 'is_team_sport': True}
        result = self.api.parsed_expression(body, EvaluationContext(body))
        self.assertEqual(result, {'case_type': 'sport', 'case_name': 'cricket', 'is_team_sport': True})
