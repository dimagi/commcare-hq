UCR Examples
============

This page lists some common examples/design patterns for user configurable reports and CommCare HQ data models.

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
    "property_value": "http://openrosa.org/formdesigner/my-registration-form"
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
        "http://openrosa.org/formdesigner/my-registration-form",
        "http://openrosa.org/formdesigner/my-follow-up-form",
        "http://openrosa.org/formdesigner/my-close-form"
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
    "property_value": "child"
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
    "property_value": ["child", "mother"]
}
```

## Filter by only open cases

NOTE: this should be changed to use boolean datatypes once those exist.

```json
{
    "type": "boolean_expression",
    "expression": {
        "type": "property_name",
        "property_name": "closed",
        "datatype": "string"

    },
    "operator": "eq",
    "property_value": "False"
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
    "display_name": "count of forms"
}
```

## Save a form property directly to a table

The following indicator stubs show how to save various properties to a data source.
These can be copied directly into data sources or modified to suit specific apps/forms.

### Submission date (received on)

This saves the submission date as a `date` object.
If you want to include the time change the datatypes to `"datetime"`.

```json
{
    "type": "expression",
    "expression": {
        "type": "property_name",
        "property_name": "received_on",
        "datatype": "date"
    },
    "display_name": "Submission date",
    "datatype": "date",
    "column_id": "received_on"
}
```

### User ID

```json
{
    "display_name": "User ID",
    "datatype": "string",
    "expression": {
        "type": "property_path",
        "property_path": [
            "form",
            "meta",
            "userID"
        ]
    },
    "is_primary_key": false,
    "transform": {},
    "is_nullable": true,
    "type": "expression",
    "column_id": "user_id"
}
```

### A text or choice property

This is the same type of indicator that should be used for typical Impact 123 indicators.
In the example below, the indicator is inside a form group question called "impact123".

```json
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

## Related doc lookups

### Get an owner name - whether it's a user, group or location

```json
{
    "datatype":"string",
    "type":"expression",
    "column_id":"owner_name",
    "expression":{
        "test":{
            "operator":"eq",
            "expression":{
                "value_expression":{
                    "type":"property_name",
                    "property_name":"doc_type"
                },
                "type":"related_doc",
                "related_doc_type":"Group",
                "doc_id_expression":{
                    "type":"property_name",
                    "property_name":"owner_id"
                }
            },
            "type":"boolean_expression",
            "property_value":"Group"
        },
        "expression_if_true":{
            "value_expression":{
                "type":"property_name",
                "property_name":"name"
            },
            "type":"related_doc",
            "related_doc_type":"Group",
            "doc_id_expression":{
                "type":"property_name",
                "property_name":"owner_id"
            }
        },
        "type":"conditional",
        "expression_if_false":{
            "type":"conditional",
            "test":{
                "operator":"eq",
                "expression":{
                    "value_expression":{
                        "type":"property_name",
                        "property_name":"doc_type"
                    },
                    "type":"related_doc",
                    "related_doc_type":"CommCareUser",
                    "doc_id_expression":{
                        "type":"property_name",
                        "property_name":"owner_id"
                    }
                },
                "type":"boolean_expression",
                "property_value":"CommCareUser"
            },
            "expression_if_true":{
                "value_expression":{
                    "type":"property_name",
                    "property_name":"username"
                },
                "type":"related_doc",
                "related_doc_type":"CommCareUser",
                "doc_id_expression":{
                    "type":"property_name",
                    "property_name":"owner_id"
                }
            },
            "expression_if_false":{
                "value_expression":{
                    "type":"property_name",
                    "property_name":"name"
                },
                "type":"related_doc",
                "related_doc_type":"Location",
                "doc_id_expression":{
                    "type":"property_name",
                    "property_name":"owner_id"
                }
            }
        }
    }
}
```


### Get a custom user data property from a form submission

```json
{
    "datatype":"string",
    "type":"expression",
    "column_id":"confirmed_referral_target",
    "expression":{
        "type":"related_doc",
        "related_doc_type":"CommCareUser",
        "doc_id_expression":{
            "type": "property_path",
            "property_path": [
                "form",
                "meta",
                "userID"
            ]
        },
        "value_expression":{
            "type":"property_path",
            "property_path": [
                "user_data",
                "confirmed_referral_target"
            ]
        }
    }
}
```

## Getting the parent case ID from a case

```json
{
    "type": "nested",
    "argument_expression": {
        "type": "array_index",
        "array_expression": {
            "type": "property_name",
            "property_name": "indices"
        },
        "index_expression": {
            "type": "constant",
            "constant": 0
        }
    },
    "value_expression": {
        "type": "property_name",
        "property_name": "referenced_id"
    }
}
```

## Getting the location type from a location doc id

`location_id_expression` can be any expression that evaluates to a valid location id.

```json
{
    "datatype":"string",
    "type":"expression",
    "expression": {
        "type": "location_type_name",
        "location_id_expression": {
            "type": "property_name",
            "property_name": "_id"
        }
    },
    "column_id": "district",
}
```

## Getting a location's parent ID

`location_id_expression` can be any expression that evaluates to a valid location id.

```json
{
    "type":"expression",
    "expression": {
        "type": "location_parent_id",
        "location_id_expression": {
            "type": "property_name",
            "property_name": "location_id"
        }
    },
    "column_id": "parent_location",
}
```

# Base Item Expressions

## Emit multiple rows (one per non-empty case property)

In this example we take 3 case properties and save one row per property if it exists.

```json
{
    "type": "iterator",
    "expressions": [
        {
            "type": "property_name",
            "property_name": "p1"
        },
        {
            "type": "property_name",
            "property_name": "p2"
        },
        {
            "type": "property_name",
            "property_name": "p3"
        },
    ],
    "test": {
        "type": "not",
        "filter": {
            "type": "boolean_expression",
            "expression": {
                "type": "identity",
            },
            "operator": "in",
            "property_value": ["", null]
        }
    }
}
```

## Emit multiple rows of complex data

In this example we take 3 case properties and emit the property name along with the value (only if non-empty).
Note that the test must also change in this scenario.


```json
{
    "type": "iterator",
    "expressions": [
        {
            "type": "dict",
            "properties": {
                "name": "p1",
                "value": {
                    "type": "property_name",
                    "property_name": "p1"
                }
            }
        },
        {
            "type": "dict",
            "properties": {
                "name": "p2",
                "value": {
                    "type": "property_name",
                    "property_name": "p2"
                }
            }
        },
        {
            "type": "dict",
            "properties": {
                "name": "p3",
                "value": {
                    "type": "property_name",
                    "property_name": "p3"
                }
            }
        }
    ],
    "test": {
        "type": "not",
        "filter": {
            "type": "boolean_expression",
            "expression": {
                "type": "property_name",
                "property_name": "value"
            },
            "operator": "in",
            "property_value": ["", null],
        }
    }
}
```

# Report examples

## Report filters

### Date filter for submission date

This assumes that you have saved a `"received_on"` column from the form into the data source.

```
{
  "type": "date",
  "slug": "received_on",
  "field": "received_on",
  "display": "Submission date",
  "required": false
}
```

## Report columns

### Creating a date column for months

The following makes a column for a `"received_on"` data source column that will aggregate by the month received.

```
{
    "type": "aggregate_date",
    "column_id": "received_on",
    "field": "received_on",
    "display": "Month"
}
```

### Expanded columns

The following snippet creates an expanded column based on a column that contains a fixed number of choices.
This is the default column setup used in Impact 123 reports.

```
{
    "type": "expanded",
    "field": "impact1",
    "column_id": "impact1",
    "display": "impact1"
}
```


# Charts

## Impact 123 grouped by date

This assumes a month-based date column and an expanded impact indicator column, as described above.


```
{
    "y_axis_columns": [
        "impact1-positive",
        "impact1-negative",
        "impact1-unknown"
    ],
    "x_axis_column": "received_on",
    "title": "Impact1 by Submission Date",
    "display_params": {},
    "aggregation_column": null,
    "type": "multibar"
}
```
