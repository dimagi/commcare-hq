from __future__ import absolute_import
from __future__ import unicode_literals
from django.utils.translation import ugettext_noop


FAILURE_MESSAGES = {
    "has_no_column": ugettext_noop(
        "Workbook 'types' has no column '{column_name}'."
    ),
    "neither_fields_nor_attributes": ugettext_noop(
        "Lookup-tables can not have empty fields and empty properties on items. "
        "table_id '{tag}' has no fields and no properties"
    ),
    "duplicate_tag": ugettext_noop(
        "Lookup-tables should have unique 'table_id'. "
        "There are two rows with table_id '{tag}' in 'types' sheet."
    ),
    "invalid_table_id": ugettext_noop(
        "table_id '{tag}' should not contain spaces or special characters, or start with a number."
    ),
    "has_no_field_column": ugettext_noop(
        "Excel worksheet '{tag}' does not contain the column 'field: {field}' "
        "as specified in its 'types' definition"
    ),
    "has_extra_column": ugettext_noop(
        "Excel worksheet '{tag}' has an extra column"
        "'field: {field}' that's not defined in its 'types' definition"
    ),
    "wrong_property_syntax": ugettext_noop(
        "Properties should be specified as 'field 1: property 1'. In 'types' sheet, "
        "'{prop_key}' is not correctly formatted"
    ),
    "wrong_index_syntax": ugettext_noop(
        "'{prop_key}' is not correctly formatted in 'types' sheet. Whether a field is indexed should be specified "
        "as 'field 1: is_indexed?'. Its value should be 'yes' or 'no'."
    ),
    "invalid_field_name_numerical": ugettext_noop(
        "Error in 'types' sheet for 'field {i}', '{val}'. "
        "Field names should be strings, not numbers"
    ),
    "invalid_field_syntax": ugettext_noop(
        "In Excel worksheet '{tag}', field '{field}' should be numbered as 'field: {field} integer",
    ),
    "sheet_has_no_property": ugettext_noop(
        "Excel worksheet '{tag}' does not contain property "
        "'{property}' of the field '{field}' as specified in its 'types' definition"
    ),
    "sheet_has_extra_property": ugettext_noop(
        "Excel worksheet '{tag}' has an extra property "
        "'{property}' for the field '{field}' that's not defined in its 'types' definition. "
        "Re-check the formatting"
    ),
    "invalid_field_with_property": ugettext_noop(
        "Fields with attributes should be numbered as 'field: {field} integer'"
    ),
    "invalid_property": ugettext_noop(
        "Attribute should be written as '{field}: {prop} integer'"
    ),
    "wrong_field_property_combos": ugettext_noop(
        "Number of values for field '{field}' and attribute '{prop}' should be same"
    ),
    "type_has_no_sheet": ugettext_noop(
        "There's no sheet for type '{type}' in 'types' sheet. "
        "There must be one sheet per row in the 'types' sheet.",
    ),
    "no_types_sheet": ugettext_noop(
        "Workbook does not contain a sheet called types"
    ),
}
