from django.test import SimpleTestCase
from couchexport.schema import extend_schema


class ExtendSchemaTest(SimpleTestCase):

    def setUp(self):
        pass

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

        new_schema = extend_schema(None, schema)
        self.assertEquals(new_schema, schema, 'Initial schema should just be what is sent in')

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

        new_schema = extend_schema(previous_schema, schema_repeat_deleted)
        self.assertEquals(
            new_schema,
            previous_schema,
        )
