from __future__ import absolute_import
from django.test import SimpleTestCase

from corehq.apps.userreports.expressions.factory import ExpressionFactory


class TestConcatenateExpression(SimpleTestCase):

    def test_concatenate_expressions_without_nulls(self):
        getter = ExpressionFactory.from_spec({
            'type': 'concatenate_strings',
            'expressions': [
                {
                    "type": "property_name",
                    "property_name": "first_name"
                },
                {
                    "type": "property_name",
                    "property_name": "last_name"
                }
            ],
            "separator": ' '
        })
        self.assertEqual(
            getter({'first_name': 'TestFirstName', 'last_name': 'TestLastName'}),
            'TestFirstName TestLastName'
        )

    def test_concatenate_expressions_with_null(self):
        getter = ExpressionFactory.from_spec({
            'type': 'concatenate_strings',
            'expressions': [
                {
                    "type": "property_name",
                    "property_name": "first_name"
                },
                {
                    "type": "property_name",
                    "property_name": "last_name"
                }
            ],
            "separator": ' '
        })
        self.assertEqual(
            getter({'first_name': 'TestFirstName', 'last_name': None}),
            'TestFirstName'
        )

    def test_concatenate_expressions_with_empty_string(self):
        getter = ExpressionFactory.from_spec({
            'type': 'concatenate_strings',
            'expressions': [
                {
                    "type": "property_name",
                    "property_name": "first_name"
                },
                {
                    "type": "property_name",
                    "property_name": "last_name"
                }
            ],
            "separator": ' '
        })
        self.assertEqual(
            getter({'first_name': 'TestFirstName', 'last_name': ''}),
            'TestFirstName'
        )

    def test_concatenate_expressions_with_missing_property(self):
        getter = ExpressionFactory.from_spec({
            'type': 'concatenate_strings',
            'expressions': [
                {
                    "type": "property_name",
                    "property_name": "first_name"
                },
                {
                    "type": "property_name",
                    "property_name": "last_name"
                }
            ],
            "separator": ' '
        })
        self.assertEqual(
            getter({'first_name': 'TestFirstName'}),
            'TestFirstName'
        )
