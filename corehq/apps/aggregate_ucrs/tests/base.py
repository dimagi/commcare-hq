from __future__ import absolute_import
from __future__ import unicode_literals
import os
import yaml

from corehq.apps.aggregate_ucrs.parser import AggregationSpec
from corehq.util.test_utils import TestFileMixin


class AggregationBaseTestMixin(TestFileMixin):
    file_path = ('data', 'table_definitions')
    root = os.path.dirname(__file__)

    def get_config_json(self):
        config_yml = self.get_file('aggregate_sample_definition', 'yml')
        return yaml.load(config_yml)

    def get_config_spec(self):
        return AggregationSpec.wrap(self.get_config_json())
