from django.test import SimpleTestCase

from corehq.apps.aggregate_ucrs.tests.base import AggregationBaseTestMixin


class ConfigParseTest(SimpleTestCase, AggregationBaseTestMixin):

    def test_parse_basic_definition(self):
        spec = self.get_monthly_config_spec()
        self.assertEqual('550c3cd432d931387e75e8506b5caf9e', spec.primary_table.data_source_id)
        self.assertEqual('doc_id', spec.primary_table.key_column)
        self.assertEqual(4, len(spec.primary_table.columns))
        self.assertEqual('month', spec.time_aggregation.unit)
        self.assertEqual('opened_date', spec.time_aggregation.start_column)
        self.assertEqual('closed_date', spec.time_aggregation.end_column)
        self.assertEqual(1, len(spec.secondary_tables))
        secondary_table = spec.secondary_tables[0]
        self.assertEqual('d824a4864ecb421fb3be8bf8173a05d7', secondary_table.data_source_id)
        self.assertEqual('doc_id', secondary_table.join_column_primary)
        self.assertEqual('form.case.@case_id', secondary_table.join_column_secondary)
        self.assertEqual('received_on', secondary_table.time_window_column)
        self.assertEqual(2, len(secondary_table.columns))
