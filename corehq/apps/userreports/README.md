User Configurable Reporting
===========================

An overview of the design, API and data structures used here.

# Data Flow

Reporting is handled in multiple stages. Here is the basic workflow.

Raw data (form or case) → [Data source config] → Row in database table → [Report config] → Report in HQ

Both the data source config and report config are JSON documents that live in the database. The data source config determines how raw data (forms and cases) gets mapped to rows in an intermediary table, while the report config(s) determine how that report table gets turned into an interactive report in the UI.

# Data Sources

Each data source configuration maps a filtered set of the raw data to indicators. A data source configuration consists of two primary sections:

1. A filter that determines whether the data is relevant for the data source
2. A list of indicators in that data source

In addition to these properties there are a number of relatively self-explanatory fields on a data source such as the `table_id` and `display_name`.

## Data Source Filtering

When setting up a data source configuration, filtering defines what data applies to a given set of indicators. Some example uses of filtering on a data source include:

- Restricting the data by document type (e.g. cases or forms). This is a built-in filter.
- Limiting the data to a particular case or form type
- Excluding demo user data
- Excluding closed cases
- Only showing data that meets a domain-specific condition (e.g. pregnancy cases opened for women over 30 years of age)

### Filter type overview

There are currently four supported filter types. However, these can be used together to produce arbitrarily complicated expressions.


Filter Type        | Description
------------------ | -----------
boolean_expression | A expression / logic statement (more below)
and                | An "and" of other filters - true if all are true
or                 | An "or" of other filters - true if any are true
not                | A "not" or inverse expression on a filter

To understand the `boolean_expression` type, we must first explain expressions.

### Expressions

An *expression* is a way of representing a set of operations that should return a single value. Expressions can basically be thought of as functions that take in a document and return a value:

*Expression*: `function(document) → value`

In normal math/python notation, the following are all valid expressions on a `doc` (which is presumed to be a `dict` object:

- `"hello"`
- `7`
- `doc["name"]`
- `doc["child"]["age"]`
- `doc["age"] < 21`
- `"legal" if doc["age"] > 21 else "underage"`

In user configurable reports the following expression types are currently supported (note that this can and likely will be extended in the future):

Expression Type | Description  | Example
--------------- | ------------ | ------
constant        | A constant   | `"hello"`, `4`, `2014-12-20`
property_name   | A reference to the property in a document |  `doc["name"]`
property_path   | A nested reference to a property in a document | `doc["child"]["age"]`
conditional     | An if/else expression | `"legal" if doc["age"] > 21 else "underage"`

### JSON snippets for expressions

Here are JSON snippets for the four expression types. Hopefully they are self-explanatory.

##### Constant Expression

This expression returns the constant "hello":
```
{
    "type": "constant",
    "constant": "hello"
}
```
##### Property Name Expression

This expression returns `doc["age"]`:
```
{
    "type": "property_name",
    "property_name": "age"
}
```
##### Property Path Expression

This expression returns `doc["child"]["age"]`:
```
{
    "type": "property_name",
    "property_path": ["child", "age"]
}
```
##### Conditional Expression

This expression returns `"legal" if doc["age"] > 21 else "underage"`:
```
{
    "test": {
        "operator": "gt",
        "expression": {
            "type": "property_name",
            "property_name": "age"
        },
        "type": "boolean_expression",
        "property_value": 21
    },
    "expression_if_true": {
        "type": "constant",
        "property_name": "legal"
    },
    "type": "conditional",
    "expression_if_false": {
        "type": "constant",
        "property_name": "underage"
    }
}
```
Note that this expression contains other expressions inside it! This is why expressions are powerful. (It also contains a filter, but we haven't covered those yet - if you find the `"test"` section confusing, keep reading...)

### Boolean Expression Filters

A `boolean_expression` filter combines an *expression*, an *operator*, and a *property value* (a constant), to produce a statement that is either `True` or `False`. *Note: in the future the constant value may be replaced with a second expression to be more general, however currently only constant property values are supported.*

Here is a sample JSON format for simple `boolean_expression` filter:
```
{
    "type": "boolean_expression",
    "expression": {
        "type": "property_name",
        "property_name": "age",
    },
    "operator": "gt",
    "property_value": 21
}
```
This is equivalent to the python statement: `doc["age"] > 21`

#### Operators

The following operators are currently supported:
Operator   | Description  | Value type | Example
---------- | -----------  | ---------- | -------
`eq`       | is equal     | constant   | `doc["age"] == 21`
`not_eq`   | is not equal | constant   | `doc["age"] != 21`
`in`       | single value is in a list | list | `doc["color"] in ["red", "blue"]`
`in_multi` | multiselect value is in a list | list | `selected(doc["color"], ["red", "blue"])`
`lt`       | is less than | number | `doc["age"] < 21`
`lte`      | is less than or equal | number | `doc["age"] <= 21`
`gt`       | is greater than | number | `doc["age"] > 21`
`gte`      | is greater than or equal | number | `doc["age"] >= 21`

### Compound filters

Compound filters build on top of `boolean_expression` filters to create boolean logic. These can be combined to support arbitrarily complicated boolean logic on data. There are three types of filters, *and*, *or*, and *not* filters. The JSON representation of these is below. Hopefully these are self explanatory.

#### "And" Filters

The following filter represents the statement: `doc["age"] < 21 and doc["nationality"] == "american"`:
```
{
    "type": "and",
    "filters": [
		{
            "type": "boolean_expression",
            "expression": {
                "type": "property_name",
                "property_name": "age",
            },
            "operator": "lt",
            "property_value": 21
        },
        {
            "type": "boolean_expression",
            "expression": {
                "type": "property_name",
                "property_name": "nationality",
            },
            "operator": "eq",
            "property_value": "american"
        }
    ]
}
```
#### "Or" Filters

The following filter represents the statement: `doc["age"] > 21 or doc["nationality"] == "european"`:
```
{
    "type": "or",
    "filters": [
		{
            "type": "boolean_expression",
            "expression": {
                "type": "property_name",
                "property_name": "age",
            },
            "operator": "gt",
            "property_value": 21
        },
		{
            "type": "boolean_expression",
            "expression": {
                "type": "property_name",
                "property_name": "nationality",
            },
            "operator": "eq",
            "property_value": "european"
        }
    ]
}
```
#### "Not" Filters

The following filter represents the statement: `!(doc["nationality"] == "european")`:
```
{
    "type": "not",
    "filter": [
        {
            "type": "boolean_expression",
            "expression": {
                "type": "property_name",
                "property_name": "nationality",
            },
            "operator": "eq",
            "property_value": "european"
        }
    ]
}
```
*Note that this could be represented more simply using a single filter with the `not_eq` operator, but "not" filters can represent more complex logic than operators generally, since the filter itself can be another compound filter.*

### Practical Examples

Below are some practical examples showing various filter types.

#### Matching form submissions from a particular form type

```
{
    "type": "boolean_expression",
    "expression": {
        "type": "property_name",
        "property_name": "xmlns",
    },
    "operator": "eq",
    "property_value": "http://openrosa.org/formdesigner/my-registration-form"
}
```
#### Matching cases of a specific type

```
{
    "type": "boolean_expression",
    "expression": {
        "type": "property_name",
        "property_name": "type",
    },
    "operator": "eq",
    "property_value": "child"
}
```

# Practical Notes

Some rough notes for working with user configurable reports.

## Getting Started


The easiest way to get started is to start with sample data and reports.

First copy the dimagi domain to your developer machine.
You only really need forms, users, and cases:

```
./manage.py copy_domain https://<your_username>:<your_password>@commcarehq.cloudant.com/commcarehq dimagi --include=CommCareCase,XFormInstance,CommCareUser
```

Then load and rebuild the data table:

```
./manage.py load_spec corehq/apps/userreports/examples/dimagi/dimagi-case-data-source.json --rebuild
```

Then load the report:

```
./manage.py load_spec corehq/apps/userreports/examples/dimagi/dimagi-chart-report.json
```

Fire up a browser and you should see the new report in your domain.
You should also be able to navigate to the edit UI, or look at and edit the example JSON files.
There is a second example based off the "gsid" domain as well using forms.

The tests are also a good source of documentation for the various filter and indicator formats that are supported.


## Inspecting database tables


The easiest way to inspect the database tables is to use the sql command line utility.
This can be done by runnning `./manage.py dbshell` or using `psql`.
The naming convention for tables is: `configurable_indicators_[domain name]_[table id]_[hash]`.
In postgres, you can see all tables by typing `\dt` and use sql commands to inspect the appropriate tables.
