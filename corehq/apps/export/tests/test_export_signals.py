from django.test import TestCase

from corehq.apps.export.signals import added_inferred_export_properties
from corehq.apps.export.dbaccessors import get_inferred_schema


class InferredSchemaSignalTest(TestCase):
    domain = 'inferred-domain'
    case_type = 'inferred'

    def test_add_inferred_export_properties(self):
        props = set(['one', 'two'])
        added_inferred_export_properties.send(
            'TestSend',
            domain=self.domain,
            case_type=self.case_type,
            properties=props,
        )

        schema = get_inferred_schema(self.domain, self.case_type)
        group_schema = schema.group_schemas[0]
        self.assertEqual(set(map(lambda item: item.path[0].name, group_schema.items)), props)

    def test_add_inferred_export_properties_saved_schema(self):
        props = set(['one', 'two'])
        props_two = set(['one', 'three'])
        added_inferred_export_properties.send(
            'TestSend',
            domain=self.domain,
            case_type=self.case_type,
            properties=props,
        )
        added_inferred_export_properties.send(
            'TestSend',
            domain=self.domain,
            case_type=self.case_type,
            properties=props_two,
        )

        schema = get_inferred_schema(self.domain, self.case_type)
        group_schema = schema.group_schemas[0]
        self.assertEqual(
            set(map(lambda item: item.path[0].name, group_schema.items)),
            set(['one', 'two', 'three'])
        )
