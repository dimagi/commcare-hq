from __future__ import absolute_import
from __future__ import unicode_literals
import yaml

from dimagi.ext import jsonobject


class PrimaryColumnSpec(jsonobject.JsonObject):
    column_id = jsonobject.StringProperty(required=True)
    type = jsonobject.StringProperty(required=True)
    config_params = jsonobject.DictProperty()


class PrimaryTableSpec(jsonobject.JsonObject):
    data_source_id = jsonobject.StringProperty(required=True)
    key_column = jsonobject.StringProperty(required=True, default='doc_id')
    columns = jsonobject.ListProperty(PrimaryColumnSpec)


class AggregationConfigSpec(jsonobject.JsonObject):
    unit = jsonobject.StringProperty(required=True)
    start_column = jsonobject.StringProperty(required=True)
    end_column = jsonobject.StringProperty(required=True)


class SecondaryColumnSpec(jsonobject.JsonObject):
    column_id = jsonobject.StringProperty(required=True)
    aggregation_type = jsonobject.StringProperty(required=True)
    config_params = jsonobject.DictProperty()


class SecondaryTableSpec(jsonobject.JsonObject):
    data_source_id = jsonobject.StringProperty(required=True)
    key_column = jsonobject.StringProperty(required=True)
    aggregation_column = jsonobject.StringProperty(required=True)
    columns = jsonobject.ListProperty(SecondaryColumnSpec)


class AggregationSpec(jsonobject.JsonObject):
    domain = jsonobject.StringProperty(required=True)
    table_id = jsonobject.StringProperty(required=True)
    display_name = jsonobject.StringProperty()
    primary_table = jsonobject.ObjectProperty(PrimaryTableSpec)
    aggregation_config = jsonobject.ObjectProperty(AggregationConfigSpec)
    secondary_tables = jsonobject.ListProperty(SecondaryTableSpec)
