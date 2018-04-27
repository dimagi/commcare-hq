from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import TestCase

from corehq.apps.aggregate_ucrs.models import AggregateTableDefinition
from corehq.apps.aggregate_ucrs.tests.base import AggregationBaseTestMixin
from corehq.apps.aggregate_ucrs.importer import import_aggregation_models_from_spec


class ConfigImportTest(TestCase, AggregationBaseTestMixin):

    def setUp(self):
        AggregateTableDefinition.objects.all().delete()

    def test_import_from_basic_definition(self):
        spec = self.get_config_spec()
        aggregate_table_definition = import_aggregation_models_from_spec(spec)
        self.assertEqual(1, AggregateTableDefinition.objects.count())
        table_def = AggregateTableDefinition.objects.get(pk=aggregate_table_definition.pk)
        self.assertEqual('550c3cd432d931387e75e8506b5caf9e', table_def.primary_data_source_id.hex)
        self.assertEqual(4, table_def.primary_columns.count())
        self.assertEqual(1, table_def.secondary_tables.count())
        secondary_table = table_def.secondary_tables.get()
        self.assertEqual('d824a4864ecb421fb3be8bf8173a05d7', secondary_table.data_source.hex)
        self.assertEqual('case_id', secondary_table.data_source_key)
        self.assertEqual('received_on', secondary_table.aggregation_column)
        self.assertEqual(1, secondary_table.columns.count())
        secondary_column = secondary_table.columns.get()
        self.assertEqual('fu_forms_in_month', secondary_column.column_id)


