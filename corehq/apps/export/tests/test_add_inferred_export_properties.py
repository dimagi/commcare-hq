from unittest.mock import patch
from django.core.cache import caches, DEFAULT_CACHE_ALIAS
from django.test import TestCase

from corehq.apps.data_dictionary.models import CaseProperty, CaseType
from corehq.apps.export.dbaccessors import (
    delete_all_export_data_schemas,
    get_case_inferred_schema,
)
from corehq.apps.export.models import ExportItem, ScalarItem
from corehq.apps.export.tasks import add_inferred_export_properties


class InferredSchemaSignalTest(TestCase):
    domain = 'inferred-domain'
    case_type = 'inferred'

    def tearDown(self):
        delete_all_export_data_schemas()
        CaseType.objects.filter(domain=self.domain, name=self.case_type).delete()
        caches['locmem'].clear()
        caches[DEFAULT_CACHE_ALIAS].clear()

    def _add_props(self, props, num_queries=3):
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

    @patch('corehq.apps.data_dictionary.models.domain_has_privilege', return_value=True)
    def test_add_inferred_export_properties(self, mock_domain_has_privilege):
        props = set(['one', 'two'])
        self._add_props(props)
        schema = get_case_inferred_schema(self.domain, self.case_type)
        group_schema = schema.group_schemas[0]
        self.assertEqual(set([item.path[0].name for item in group_schema.items]), props)
        self._check_sql_props(props)

    @patch('corehq.apps.data_dictionary.models.domain_has_privilege', return_value=True)
    def test_add_inferred_export_properties_saved_schema(self, mock_domain_has_privilege):
        props = set(['one', 'two'])
        props_two = set(['one', 'three'])
        combined_props = props | props_two
        self._add_props(props)
        self._add_props(props_two)

        schema = get_case_inferred_schema(self.domain, self.case_type)
        group_schema = schema.group_schemas[0]
        self.assertEqual(
            set([item.path[0].name for item in group_schema.items]),
            combined_props
        )
        self.assertTrue(
            all([isinstance(item, ScalarItem) for item in group_schema.items]),
        )
        self._check_sql_props(combined_props)

    @patch('corehq.apps.data_dictionary.models.domain_has_privilege', return_value=True)
    def test_add_inferred_export_properties_system(self, mock_domain_has_privilege):
        """
        Ensures that when we add a system property, it uses the system's item type
        """
        props = set(['closed'])
        self._add_props(props)
        schema = get_case_inferred_schema(self.domain, self.case_type)
        group_schema = schema.group_schemas[0]
        self.assertEqual(len(group_schema.items), 1)
        self.assertEqual(group_schema.items[0].__class__, ExportItem)
        self._check_sql_props(props)

    @patch('corehq.apps.data_dictionary.models.domain_has_privilege', return_value=True)
    def test_add_inferred_export_properties_system_with_transform(self, mock_domain_has_privilege):
        """
        Ensures that when we add a system property with redundant paths, it uses the item's transform
        """
        props = set(['user_id'])  # user_id maps to two system properties
        self._add_props(props)
        schema = get_case_inferred_schema(self.domain, self.case_type)
        group_schema = schema.group_schemas[0]
        self.assertEqual(len(group_schema.items), 1)

    @patch('corehq.apps.data_dictionary.models.domain_has_privilege', return_value=True)
    def test_cache_add_inferred_export_properties(self, mock_domain_has_privilege):
        props = set(['one', 'two'])
        self._add_props(props)
        self._add_props(props, 0)
