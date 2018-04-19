from __future__ import absolute_import
from __future__ import unicode_literals
import os

import yaml
from django.test import SimpleTestCase

from corehq.util.test_utils import TestFileMixin
from corehq.apps.aggregate_ucrs.parser import AggregationSpec


class ConfigParseTest(SimpleTestCase, TestFileMixin):
    file_path = ('data', 'table_definitions')
    root = os.path.dirname(__file__)

    def test_parse_basic_definition(self):
        config_yml = self.get_file('aggregate_sample_definition', 'yml')
        config_json = yaml.load(config_yml)
        spec = AggregationSpec.wrap(config_json)
        self.assertEqual('pregnancy_cases', spec.primary_table.data_source_id)
        self.assertEqual('doc_id', spec.primary_table.key_column)
        self.assertEqual(4, len(spec.primary_table.columns))
        self.assertEqual('month', spec.aggregation_config.unit)
        self.assertEqual('date_opened', spec.aggregation_config.start_column)
        self.assertEqual('date_closed', spec.aggregation_config.end_column)
        self.assertEqual(1, len(spec.secondary_tables))
        secondary_table = spec.secondary_tables[0]
        self.assertEqual('followup_forms', secondary_table.data_source_id)
        self.assertEqual('case_id', secondary_table.key_column)
        self.assertEqual('received_on', secondary_table.aggregation_column)
        self.assertEqual(1, len(secondary_table.columns))
