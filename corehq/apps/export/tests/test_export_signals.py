from django.test import TestCase

from corehq.apps.export.tasks import add_inferred_export_properties
from corehq.apps.export.dbaccessors import get_inferred_schema, delete_all_inferred_schemas
from corehq.apps.export.models import ScalarItem, ExportItem


class InferredSchemaSignalTest(TestCase):
    domain = 'inferred-domain'
    case_type = 'inferred'

    def setUp(self):
        delete_all_inferred_schemas()

    def test_add_inferred_export_properties(self):
        props = set(['one', 'two'])
        add_inferred_export_properties(
            'TestSend',
            self.domain,
            self.case_type,
            props,
        )

        schema = get_inferred_schema(self.domain, self.case_type)
        group_schema = schema.group_schemas[0]
        self.assertEqual(set(map(lambda item: item.path[0].name, group_schema.items)), props)

    def test_add_inferred_export_properties_saved_schema(self):
        props = set(['one', 'two'])
        props_two = set(['one', 'three'])
        add_inferred_export_properties(
            'TestSend',
            self.domain,
            self.case_type,
            props,
        )
        add_inferred_export_properties(
            'TestSend',
            self.domain,
            self.case_type,
            props_two,
        )

        schema = get_inferred_schema(self.domain, self.case_type)
        group_schema = schema.group_schemas[0]
        self.assertEqual(
            set(map(lambda item: item.path[0].name, group_schema.items)),
            set(['one', 'two', 'three'])
        )
        self.assertTrue(
            all(map(lambda item: isinstance(item, ScalarItem), group_schema.items)),
        )

    def test_add_inferred_export_properties_system(self):
        """
        Ensures that when we add a system property, it uses the system's item type
        """
        props = set(['closed'])
        add_inferred_export_properties(
            'TestSend',
            self.domain,
            self.case_type,
            props,
        )
        schema = get_inferred_schema(self.domain, self.case_type)
        group_schema = schema.group_schemas[0]
        self.assertEqual(len(group_schema.items), 1)
        self.assertEqual(group_schema.items[0].__class__, ExportItem)
