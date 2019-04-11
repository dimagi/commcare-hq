from __future__ import absolute_import
from __future__ import unicode_literals
import os
import yaml

from corehq.apps.aggregate_ucrs.parser import AggregationSpec
from corehq.util.test_utils import TestFileMixin


class AggregationBaseTestMixin(TestFileMixin):
    file_path = ('data', 'table_definitions')
    root = os.path.dirname(__file__)

    @classmethod
    def get_monthly_config_json(cls):
        config_yml = cls.get_file('monthly_aggregate_definition', 'yml')
        return yaml.safe_load(config_yml)

    @classmethod
    def get_monthly_config_spec(cls):
        return AggregationSpec.wrap(cls.get_monthly_config_json())

    @classmethod
    def get_basic_config_json(cls):
        config_yml = cls.get_file('basic_aggregate_definition', 'yml')
        return yaml.safe_load(config_yml)

    @classmethod
    def get_basic_config_spec(cls):
        return AggregationSpec.wrap(cls.get_basic_config_json())
