from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import SimpleTestCase

from corehq.apps.export.models import (
    InferredSchema,
    InferredExportGroupSchema,
    PathNode,
    ExportItem
)


class InferredSchemaTest(SimpleTestCase):

    def test_put_group_schema(self):
        schema = InferredSchema(
            domain='inferred-domain',
            case_type='inferred',
        )
        group_schema = schema.put_group_schema(
            [PathNode(name='random'), PathNode(name='table')],
        )

        self.assertTrue(isinstance(group_schema, InferredExportGroupSchema))
        self.assertTrue(group_schema.inferred)
        self.assertEqual(len(schema.group_schemas), 1)

        # After putting same group schema, should not re-add group schema
        group_schema = schema.put_group_schema(
            [PathNode(name='random'), PathNode(name='table')],
        )
        self.assertEqual(len(schema.group_schemas), 1)


class InferredExportGroupSchemaTest(SimpleTestCase):

    def test_put_export_item(self):
        group_schema = InferredExportGroupSchema(
            path=[PathNode(name='random')]
        )
        item = group_schema.put_item(
            [PathNode(name='random'), PathNode(name='inferred')],
            inferred_from='Test',
        )
        item = group_schema.put_item(
            [PathNode(name='random'), PathNode(name='inferred')],
            inferred_from='TestTwo',
        )
        self.assertTrue(isinstance(item, ExportItem))
        self.assertTrue(item.inferred)
        self.assertEqual(item.inferred_from, set(['Test', 'TestTwo']))
        self.assertEqual(len(group_schema.items), 1)

        # After putting same item, should not re-add group schema
        item = group_schema.put_item(
            [PathNode(name='random'), PathNode(name='inferred')],
        )
        self.assertEqual(len(group_schema.items), 1)
