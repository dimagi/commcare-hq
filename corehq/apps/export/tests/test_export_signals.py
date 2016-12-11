from django.test import TestCase

from corehq.apps.data_dictionary.models import CaseType, CaseProperty
from corehq.apps.export.tasks import add_inferred_export_properties
from corehq.apps.export.dbaccessors import get_inferred_schema, delete_all_inferred_schemas
from corehq.apps.export.models import ScalarItem, ExportItem


class InferredSchemaSignalTest(TestCase):
    domain = 'inferred-domain'
    case_type = 'inferred'

    def tearDown(self):
        delete_all_inferred_schemas()
        CaseType.objects.filter(domain=self.domain, name=self.case_type).delete()

    def _add_props(self, props, num_queries=5):
        # should be 3, but the transaction in tests adds two when creating a case type
        with self.assertNumQueries(num_queries):
            add_inferred_export_properties(
                'TestSend',
                self.domain,
                self.case_type,
                props,
            )

    def _check_sql_props(self, props):
        sql_props = CaseProperty.objects.filter(
            case_type__domain=self.domain, case_type__name=self.case_type
        )
        dd_props = {c.name for c in sql_props}
        self.assertEqual(dd_props, props)

    def test_add_inferred_export_properties(self):
        props = set(['one', 'two'])
        self._add_props(props)
        schema = get_inferred_schema(self.domain, self.case_type)
        group_schema = schema.group_schemas[0]
        self.assertEqual(set(map(lambda item: item.path[0].name, group_schema.items)), props)
        self._check_sql_props(props)

    def test_add_inferred_export_properties_saved_schema(self):
        props = set(['one', 'two'])
        props_two = set(['one', 'three'])
        combined_props = props | props_two
        self._add_props(props)
        self._add_props(props_two, 3)

        schema = get_inferred_schema(self.domain, self.case_type)
        group_schema = schema.group_schemas[0]
        self.assertEqual(
            set(map(lambda item: item.path[0].name, group_schema.items)),
            combined_props
        )
        self.assertTrue(
            all(map(lambda item: isinstance(item, ScalarItem), group_schema.items)),
        )
        self._check_sql_props(combined_props)

    def test_add_inferred_export_properties_system(self):
        """
        Ensures that when we add a system property, it uses the system's item type
        """
        props = set(['closed'])
        self._add_props(props)
        schema = get_inferred_schema(self.domain, self.case_type)
        group_schema = schema.group_schemas[0]
        self.assertEqual(len(group_schema.items), 1)
        self.assertEqual(group_schema.items[0].__class__, ExportItem)
        self._check_sql_props(props)
