"""
Classes responsible for creating/validating aggregate ucr specs
in their json/yaml formats.

These objects are only used to parse the configs and generate / import
the django models.

They may be able to be replaced with django rest framework serializers.
"""

from dimagi.ext import jsonobject


class PrimaryColumnSpec(jsonobject.JsonObject):
    column_id = jsonobject.StringProperty(required=True)
    type = jsonobject.StringProperty(required=True)
    config_params = jsonobject.DictProperty()


class PrimaryTableSpec(jsonobject.JsonObject):
    data_source_id = jsonobject.StringProperty(required=True)
    key_column = jsonobject.StringProperty(required=True, default='doc_id')
    columns = jsonobject.ListProperty(PrimaryColumnSpec)


class TimeAggregationConfigSpec(jsonobject.JsonObject):
    unit = jsonobject.StringProperty(required=True)
    start_column = jsonobject.StringProperty(required=True)
    end_column = jsonobject.StringProperty(required=True)


class SecondaryColumnSpec(jsonobject.JsonObject):
    column_id = jsonobject.StringProperty(required=True)
    aggregation_type = jsonobject.StringProperty(required=True)
    config_params = jsonobject.DictProperty()


class SecondaryTableSpec(jsonobject.JsonObject):
    data_source_id = jsonobject.StringProperty(required=True)
    join_column_primary = jsonobject.StringProperty(required=True)
    join_column_secondary = jsonobject.StringProperty(required=True)
    time_window_column = jsonobject.StringProperty()
    columns = jsonobject.ListProperty(SecondaryColumnSpec)


class AggregationSpec(jsonobject.JsonObject):
    domain = jsonobject.StringProperty(required=True)
    table_id = jsonobject.StringProperty(required=True)
    display_name = jsonobject.StringProperty()
    primary_table = jsonobject.ObjectProperty(PrimaryTableSpec)
    time_aggregation = jsonobject.ObjectProperty(TimeAggregationConfigSpec)
    secondary_tables = jsonobject.ListProperty(SecondaryTableSpec)
