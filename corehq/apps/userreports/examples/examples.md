UCR Examples
============

This page lists some common examples/design patterns for user configurable reports and CommCare HQ data models.

Arguments listed inside `"[brackets]"` are meant to be replaced.

# Data source filters

The following are example filter expressions that are common in data sources.

## Filters on forms

The following filters apply to data sources built on top of forms.

### Filter by a specific form type using the XMLNS

```
{
    "type": "boolean_expression",
    "expression": {
        "type": "property_name",
        "property_name": "xmlns"
    },
    "operator": "eq",
    "property_value": "[http://openrosa.org/formdesigner/my-registration-form]"
}
```
### Filter by a set of form types using the XMLNS

```
{
    "type": "boolean_expression",
    "expression": {
        "type": "property_name",
        "property_name": "xmlns"
    },
    "operator": "in",
    "property_value": [
        "[http://openrosa.org/formdesigner/my-registration-form]",
        "[http://openrosa.org/formdesigner/my-follow-up-form]",
        "[http://openrosa.org/formdesigner/my-close-form]"
    ]
}
```

## Filters on cases

The following filters apply to data sources built on top of cases.

## Filter by a specific case type

```
{
    "type": "boolean_expression",
    "expression": {
        "type": "property_name",
        "property_name": "type"
    },
    "operator": "eq",
    "property_value": "[child]"
}
```
## Filter by multiple case types

```
{
    "type": "boolean_expression",
    "expression": {
        "type": "property_name",
        "property_name": "type"
    },
    "operator": "in",
    "property_value": ["[child]", "[mother]"]
}
```

# Data source indicators

## Count every contributing row (form or case)

```
{
    "type": "expression",
    "expression": {
        "type": "constant",
        "constant": 1
    },
    "column_id": "count",
    "datatype": "integer",
    "display_name": "[count of forms]"
}
```

## Save a form property directly to a table

This is the same type of indicator that should be used for typical Impact 123 indicators.
In the example below, the indicator is inside a form group question called "impact123".

```
{
    "type": "expression",
    "expression": {
        "type": "property_path",
        "property_path": ["form", "impact123", "cc_impact_1"]
    },
    "column_id": "impact1",
    "display_name": "Impact 1",
    "datatype": "string"
}
```
