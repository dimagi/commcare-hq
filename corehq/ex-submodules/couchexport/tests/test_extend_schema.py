from copy import deepcopy

from django.test import SimpleTestCase
from couchexport.schema import extend_schema


class ExtendSchemaTest(SimpleTestCase):

    def test_simple_schema(self):
        """
        Testing the initial generation of the schema
        """
        schema = {
            'question1': 'string',
            'question2': {
                'inner1': 'string'
            }
        }

        expected = deepcopy(schema)

        new_schema = extend_schema(None, schema)
        self.assertEquals(new_schema, expected, 'Initial schema should just be what is sent in')

    def test_reconcile_repeat_group(self):

        schema = {
            'question1': 'string',
            'question2': {
                'inner1': 'string'
            }
        }

        # Once a repeat group has been discovered, is should convert previous schema to be a list
        schema_repeat_group = {
            'question1': 'string',
            'question2': [{
                'inner1': 'string'
            }]
        }

        new_schema = extend_schema(schema, schema_repeat_group)
        self.assertEquals(
            new_schema,
            schema_repeat_group,
        )

    def test_reconcile_delete_question_within_repeat_group(self):
        """
        This test ensures that when you delete a question within a repeat group, that question stays in
        the schema
        """

        previous_schema = {
            'question1': 'string',
            'question2': [{
                'inner1': 'string',
                'inner2': 'string',
            }]
        }

        # If a question in a repeat group has been deleted, the schema should still contain the question
        schema_repeat_deleted = {
            'question1': 'string',
            'question2': [{
                'inner1': 'string'
            }]
        }

        expected = deepcopy(previous_schema)
        new_schema = extend_schema(previous_schema, schema_repeat_deleted)
        self.assertEquals(
            new_schema,
            expected,
        )

    def test_remove_group(self):
        previous_schema = {
            'question2': {
                'question2': 'string',
            }
        }

        # If group has been removed but the questions in the group remain (and the question in the group have
        # the same name as the group itself
        schema_group_deleted = {
            'question2': 'string'
        }

        expected = {
            'question2': {
                '': 'string',
                'question2': 'string',
            }
        }
        new_schema = extend_schema(previous_schema, schema_group_deleted)
        self.assertEqual(
            new_schema,
            expected,
        )
