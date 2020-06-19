COMPUTED_USER_NAME_PROPERTY_ID = "computed/user_name"
COMPUTED_OWNER_NAME_PROPERTY_ID = "computed/owner_name"
COMPUTED_OWNER_LOCATION_PROPERTY_ID = "computed/owner_location"
COMPUTED_OWNER_LOCATION_WITH_DESENDANTS_PROPERTY_ID = "computed/owner_location_with_descendants"

UI_AGG_AVERAGE = "Average"
UI_AGG_COUNT_PER_CHOICE = "Count per Choice"
UI_AGG_GROUP_BY = "Group By"
UI_AGG_SUM = "Sum"
UI_AGGREGATIONS = (
    UI_AGG_AVERAGE,
    UI_AGG_COUNT_PER_CHOICE,
    UI_AGG_GROUP_BY,
    UI_AGG_SUM,
)

UCR_AGG_AVG = 'avg'
UCR_AGG_EXPAND = 'expand'
UCR_AGG_SIMPLE = "simple"
UCR_AGG_SUM = 'sum'
UCR_AGGREGATIONS = (
    UCR_AGG_AVG,
    UCR_AGG_EXPAND,
    UCR_AGG_SIMPLE,
    UCR_AGG_SUM,
)

PROPERTY_TYPE_META = "meta"
PROPERTY_TYPE_CASE_PROP = "case_property"
PROPERTY_TYPE_QUESTION = "question"
PROPERTY_TYPE_RAW = "raw"


# note: these values are duplicated in js/constants.js
# annoyingly, the same set of "stuff" is used for both formats and pre filters, hence
# the weird namespacing
FORMAT_CHOICE = 'Choice'
FORMAT_DATE = 'Date'
FORMAT_VALUE = 'Value'
FORMAT_NUMERIC = 'Numeric'
PRE_FILTER_VALUE_IS_EMPTY = 'Is Empty'
PRE_FILTER_VALUE_EXISTS = 'Exists'
PRE_FILTER_VALUE_NOT_EQUAL = 'Value Not Equal'


# This dict maps filter types from the report builder frontend to UCR filter types
REPORT_BUILDER_FILTER_TYPE_MAP = {
    FORMAT_CHOICE: 'dynamic_choice_list',
    FORMAT_DATE: 'date',
    FORMAT_NUMERIC: 'numeric',
    FORMAT_VALUE: 'pre',
    PRE_FILTER_VALUE_IS_EMPTY: 'is_empty',
    PRE_FILTER_VALUE_EXISTS: 'exists',
    PRE_FILTER_VALUE_NOT_EQUAL: 'value_not_equal',
}
