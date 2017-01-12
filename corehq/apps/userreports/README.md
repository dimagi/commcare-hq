User Configurable Reporting
===========================
An overview of the design, API and data structures used here.


**Table of Contents**

- [Data Flow](#data-flow)
- [Data Sources](#data-sources)
    - [Data Source Filtering](#data-source-filtering)
        - [Filter type overview](#filter-type-overview)
        - [Expressions](#expressions)
        - [JSON snippets for expressions](#json-snippets-for-expressions)
            - [Constant Expression](#constant-expression)
            - [Property Name Expression](#property-name-expression)
            - [Property Path Expression](#property-path-expression)
            - [Conditional Expression](#conditional-expression)
            - [Switch Expression](#switch-expression)
            - [Array Index Expression](#array-index-expression)
            - [Iterator Expression](#iterator-expression)
            - [Base iteration number expressions](#base-iteration-number-expressions)
            - [Related document expressions](#related-document-expressions)
            - [Nested expressions](#nested-expressions)
            - [Dict expressions](#dict-expressions)
            - ["Add Days" expressions](#add-days-expressions)
            - ["Add Months" expressions](#add-months-expressions)
            - ["Diff Days" expressions](#diff-days-expressions)
            - ["Evaluator" expression](#evaluator-expression)
            - [Function calls within evaluator expressions](#function-calls-within-evaluator-expressions)
            - ["Month Start Date" and "Month End Date" expressions](#month-start-date-and-month-end-date-expressions)
            - [Filter, Sort, Map and Reduce Expressions](#filter-sort-map-and-reduce-expressions)
                - [map_items Expression](#map_items-expression)
                - [filter_items Expression](#filte_ritems-expression)
                - [sort_items Expression](#sort_items-expression)
                - [reduce_items Expression](#reduce_items-expression)
                - [flatten_items expression](#flatten_items-expression)
            - [Named Expressions](#named-expressions)
        - [Boolean Expression Filters](#boolean-expression-filters)
            - [Operators](#operators)
        - [Compound filters](#compound-filters)
            - ["And" Filters](#and-filters)
            - ["Or" Filters](#or-filters)
            - ["Not" Filters](#not-filters)
        - [Practical Examples](#practical-examples)
    - [Indicators](#indicators)
        - [Indicator Properties](#indicator-properties)
        - [Indicator types](#indicator-types)
            - [Boolean indicators](#boolean-indicators)
            - [Expression indicators](#expression-indicators)
            - [Choice list indicators](#choice-list-indicators)
            - [Ledger Balance Indicators](#ledger-balance-indicators)
        - [Practical notes for creating indicators](#practical-notes-for-creating-indicators)
            - [Fractions](#fractions)
    - [Saving Multiple Rows per Case/Form](#saving-multiple-rows-per-caseform)
- [Report Configurations](#report-configurations)
    - [Samples](#samples)
    - [Report Filters](#report-filters)
        - [Numeric Filters](#numeric-filters)
        - [Date filters](#date-filters)
        - [Quarter filters](#quarter-filters)
        - [Dynamic choice lists](#dynamic-choice-lists)
            - [Choice providers](#choice-providers)
        - [Choice lists](#choice-lists)
        - [Internationalization](#internationalization)
    - [Report Columns](#report-columns)
        - [Field columns](#field-columns)
        - [Percent columns](#percent-columns)
            - [Formats](#formats)
        - [AggregateDateColumn](#aggregatedatecolumn)
        - [Expanded Columns](#expanded-columns)
        - [The "aggregation" column property](#the-aggregation-column-property)
            - [Column IDs](#column-ids)
        - [Calculating Column Totals](#calculating-column-totals)
        - [Internationalization](#internationalization)
    - [Aggregation](#aggregation)
        - [No aggregation](#no-aggregation)
        - [Aggregate by 'username' column](#aggregate-by-username-column)
        - [Aggregate by two columns](#aggregate-by-two-columns)
    - [Transforms](#transforms)
        - [Translations and arbitrary mappings](#translations-and-arbitrary-mappings)
        - [Displaying username instead of user ID](#displaying-username-instead-of-user-id)
        - [Displaying username minus @domain.commcarehq.org instead of user ID](#displaying-username-minus-domaincommcarehqorg-instead-of-user-id)
        - [Displaying owner name instead of owner ID](#displaying-owner-name-instead-of-owner-id)
        - [Displaying month name instead of month index](#displaying-month-name-instead-of-month-index)
        - [Rounding decimals](#rounding-decimals)
        - [Generic number formatting](#generic-number-formatting)
            - [Round to the nearest whole number](#round-to-the-nearest-whole-number)
            - [Always round to 3 decimal places](#always-round-to-3-decimal-places)
        - [Date formatting](#date-formatting)
    - [Charts](#charts)
        - [Pie charts](#pie-charts)
        - [Aggregate multibar charts](#aggregate-multibar-charts)
        - [Multibar charts](#multibar-charts)
    - [Sort Expression](#sort-expression)
- [Mobile UCR](#mobile-ucr)
    - [Filters](#filters)
        - [Custom Calendar Month](#custom-calendar-month)
- [Export](#export)
    - [Export example](#export-example)
- [Practical Notes](#practical-notes)
    - [Getting Started](#getting-started)
    - [Static data sources](#static-data-sources)
    - [Static configurable reports](#static-configurable-reports)
    - [Custom configurable reports](#custom-configurable-reports)
    - [Extending User Configurable Reports](#extending-user-configurable-reports)
    - [Inspecting database tables](#inspecting-database-tables)


# Data Flow

Reporting is handled in multiple stages. Here is the basic workflow.

Raw data (form or case) → [Data source config] → Row in database table → [Report config] → Report in HQ

Both the data source config and report config are JSON documents that live in the database. The data source config determines how raw data (forms and cases) gets mapped to rows in an intermediary table, while the report config(s) determine how that report table gets turned into an interactive report in the UI.

# Data Sources

Each data source configuration maps a filtered set of the raw data to indicators. A data source configuration consists of two primary sections:

1. A filter that determines whether the data is relevant for the data source
2. A list of indicators in that data source

In addition to these properties there are a number of relatively self-explanatory fields on a data source such as the `table_id` and `display_name`, and a few more nuanced ones. The full list of available fields is summarized in the following table:

Field                | Description
-------------------- | -----------
filter               | Determines whether the data is relevant for the data source
indicators           | List of indicators to save
table_id             | A unique ID for the table
display_name         | A display name for the table that shows up in UIs
base_item_expression | Used for making tables off of repeat or list data
named_expressions    | A list of named expressions that can be referenced in other filters and indicators
named_filters        | A list of named filters that can be referenced in other filters and indicators


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
identity        | Just returns whatever is passed in | `doc`
constant        | A constant   | `"hello"`, `4`, `2014-12-20`
property_name   | A reference to the property in a document |  `doc["name"]`
property_path   | A nested reference to a property in a document | `doc["child"]["age"]`
conditional     | An if/else expression | `"legal" if doc["age"] > 21 else "underage"`
switch          | A switch statement | `if doc["age"] == 21: "legal"` `elif doc["age"] == 60: ...` `else: ...`
array_index     | An index into an array | `doc[1]`
split_string    | Splitting a string and grabbing a specific element from it by index | `doc["foo bar"].split(' ')[0]`
iterator        | Combine multiple expressions into a list | `[doc.name, doc.age, doc.gender]`
related_doc     | A way to reference something in another document | `form.case.owner_id`
root_doc        | A way to reference the root document explicitly (only needed when making a data source from repeat/child data) | `repeat.parent.name`
nested          | A way to chain any two expressions together | `f1(f2(doc))`
dict            | A way to emit a dictionary of key/value pairs | `{"name": "test", "value": f(doc)}`
add_days        | A way to add days to a date | `my_date + timedelta(days=15)`
add_months      | A way to add months to a date | `my_date + relativedelta(months=15)`
month_start_date| First day in the month of a date | `2015-01-20` -> `2015-01-01`
month_end_date  | Last day in the month of a date | `2015-01-20` -> `2015-01-31`
diff_days       | A way to get duration in days between two dates | `(to_date - from-date).days`
evaluator       | A way to do arithmetic operations | `a + b*c / d`
base_iteration_number | Used with [`base_item_expression`](#saving-multiple-rows-per-caseform) - a way to get the current iteration number (starting from 0). | `loop.index`


Following expressions act on a list of objects or a list of lists (for e.g. on a repeat list) and return another list or value. These expressions can be combined to do complex aggregations on list data.

Expression Type | Description  | Example
--------------- | ------------ | ------
filter_items    | Filter a list of items to make a new list | `[1, 2, 3, -1, -2, -3] -> [1, 2, 3]`  (filter numbers greater than zero)
map_items       | Map one list to another list | `[{'name': 'a', gender: 'f'}, {'name': 'b, gender: 'm'}]` -> `['a', 'b']`  (list of names from list of child data)
sort_items      | Sort a list based on an expression | `[{'name': 'a', age: 5}, {'name': 'b, age: 3}]` -> `[{'name': 'b, age: 3}, {'name': 'a', age: 5}]`  (sort child data by age)
reduce_items    | Aggregate a list of items into one value | sum on `[1, 2, 3]` -> `6`
flatten_items   | Flatten multiple lists of items into one list | `[[1, 2], [4, 5]]` -> `[1, 2, 4, 5]`



### JSON snippets for expressions

Here are JSON snippets for the various expression types. Hopefully they are self-explanatory.

##### Constant Expression

There are two formats for constant expressions. The simplified format is simply the constant itself. For example `"hello"`, or `5`.

The complete format is as follows. This expression returns the constant `"hello"`:

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
An optional `"datatype"` attribute may be specified, which will attempt to cast the property to the given data type. The options are "date", "datetime", "string", "integer", and "decimal". If no datatype is specified, "string" will be used.

##### Property Path Expression

This expression returns `doc["child"]["age"]`:
```
{
    "type": "property_path",
    "property_path": ["child", "age"]
}
```
An optional `"datatype"` attribute may be specified, which will attempt to cast the property to the given data type. The options are "date", "datetime", "string", "integer", and "decimal". If no datatype is specified, "string" will be used.

##### Conditional Expression

This expression returns `"legal" if doc["age"] > 21 else "underage"`:
```
{
    "type": "conditional",
    "test": {
        "operator": "gt",
        "expression": {
            "type": "property_name",
            "property_name": "age",
            "datatype": "integer"
        },
        "type": "boolean_expression",
        "property_value": 21
    },
    "expression_if_true": {
        "type": "constant",
        "constant": "legal"
    },
    "expression_if_false": {
        "type": "constant",
        "constant": "underage"
    }
}
```
Note that this expression contains other expressions inside it! This is why expressions are powerful. (It also contains a filter, but we haven't covered those yet - if you find the `"test"` section confusing, keep reading...)

Note also that it's important to make sure that you are comparing values of the same type. In this example, the expression that retrieves the age property from the document also casts the value to an integer. If this datatype is not specified, the expression will compare a string to the `21` value, which will not produce the expected results!

##### Switch Expression

This expression returns the value of the expression for the case that matches the switch on expression. Note that case values may only be strings at this time.
```json
{
    "type": "switch",
    "switch_on": {
        "type": "property_name",
        "property_name": "district"
    },
    "cases": {
        "north": {
            "type": "constant",
            "constant": 4000
        },
        "south": {
            "type": "constant",
            "constant": 2500
        },
        "east": {
            "type": "constant",
            "constant": 3300
        },
        "west": {
            "type": "constant",
            "constant": 65
        },
    },
    "default": {
        "type": "constant",
        "constant": 0
    }
}
```

##### Array Index Expression

This expression returns `doc["siblings"][0]`:
```json
{
    "type": "array_index",
    "array_expression": {
        "type": "property_name",
        "property_name": "siblings"
    },
    "index_expression": {
        "type": "constant",
        "constant": 0
    }
}
```
It will return nothing if the siblings property is not a list, the index isn't a number, or the indexed item doesn't exist.

##### Split String Expression

This expression returns `(doc["foo bar"]).split(' ')[0]`:
```json
{
    "type": "split_string",
    "string_expression": {
        "type": "property_name",
        "property_name": "multiple_value_string"
    },
    "index_expression": {
        "type": "constant",
        "constant": 0
    },
    "delimiter": ","
}
```
The delimiter is optional and is defaulted to a space.  It will return nothing if the string_expression is not a string, or if the index isn't a number or the indexed item doesn't exist.

##### Iterator Expression

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
    "test": {}
}
```

This will emit `[doc.p1, doc.p2, doc.p3]`.
You can add a `test` attribute to filter rows from what is emitted - if you don't specify this then the iterator will include one row per expression it contains regardless of what is passed in.
This can be used/combined with the `base_item_expression` to emit multiple rows per document.


#### Base iteration number expressions

These are very simple expressions with no config. They return the index of the repeat item starting from 0 when used with a `base_item_expression`.

```json
{
    "type": "base_iteration_number"
}
```

#### Related document expressions

This can be used to lookup a property in another document. Here's an example that lets you look up `form.case.owner_id` from a form.

```
{
    "type": "related_doc",
    "related_doc_type": "CommCareCase",
    "doc_id_expression": {
        "type": "property_path",
        "property_path": ["form", "case", "@case_id"]
    },
    "value_expression": {
        "type": "property_name",
        "property_name": "owner_id"
    }
}
```

#### Nested expressions

These can be used to nest expressions. This can be used, e.g. to pull a specific property out of an item in a list of objects.

The following nested expression is the equivalent of a `property_path` expression to `["outer", "inner"]` and demonstrates the functionality.
More examples can be found in the [practical examples](https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/userreports/examples/examples.md).

```json
{
    "type": "nested",
    "argument_expression": {
        "type": "property_name",
        "property_name": "outer"
    },
    "value_expression": {
        "type": "property_name",
        "property_name": "inner"
    }
}
```

#### Dict expressions

These can be used to create dictionaries of key/value pairs. This is only useful as an intermediate structure in another expression since the result of the expression is a dictionary that cannot be saved to the database.

See the [practical examples](https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/userreports/examples/examples.md) for a way this can be used in a `base_item_expression` to emit multiple rows for a single form/case based on different properties.

Here is a simple example that demonstrates the structure. The keys of `properties` must be text, and the values must be valid expressions (or constants):

```json
{
    "type": "dict",
    "properties": {
        "name": "a constant name",
        "value": {
            "type": "property_name",
            "property_name": "prop"
        },
        "value2": {
            "type": "property_name",
            "property_name": "prop2"
        }
    }
}
```

#### "Add Days" expressions

Below is a simple example that demonstrates the structure.
The expression below will add 28 days to a property called "dob".
The date_expression and count_expression can be any valid expressions, or simply constants.

```json
{
    "type": "add_days",
    "date_expression": {
        "type": "property_name",
        "property_name": "dob",
    },
    "count_expression": 28
}
```

#### "Add Months" expressions

`add_months` offsets given date by given number of calendar months.
If offset results in an invalid day (for e.g. Feb 30, April 31), the day of resulting date will be adjusted to last day of the resulting calendar month.

The date_expression and months_expression can be any valid expressions, or simply constants, including negative numbers.

```json
{
    "type": "add_months",
    "date_expression": {
        "type": "property_name",
        "property_name": "dob",
    },
    "months_expression": 28
}
```

#### "Diff Days" expressions

`diff_days` returns number of days between dates specified by `from_date_expression` and `to_date_expression`.
The from_date_expression and to_date_expression can be any valid expressions, or simply constants.

```json
{
    "type": "diff_days",
    "from_date_expression": {
        "type": "property_name",
        "property_name": "dob",
    },
    "to_date_expression": "2016-02-01"
}
```

#### "Evaluator" expression
`evaluator` expression can be used to evaluate statements that contain arithmetic (and simple python like statements). It evaluates the statement specified by `statement` which can contain variables as defined in `context_variables`.

```json
{
    "type": "evaluator",
    "statement": "a + b - c + 6",
    "context_variables": {
        "a": 1,
        "b": 20,
        "c": 2
    }
}
```
This returns 25 (1 + 20 - 2 + 6).

`statement` can be any statement that returns a valid number. All python math [operators](https://en.wikibooks.org/wiki/Python_Programming/Basic_Math#Mathematical_Operators) except power operator are available for use.

`context_variables` is a dictionary of Expressions where keys are names of variables used in the `statement` and values are expressions to generate those variables.
Variables can be any valid numbers (Python datatypes `int`, `float` and `long` are considered valid numbers.) or also expressions that return numbers. In addition to numbers the following types are supported:

* `date`
* `datetime`

#### Function calls within evaluator expressions
Only the following functions are permitted:

* `rand()`: generate a random number between 0 and 1
* `randint(max)`: generate a random integer between 0 and `max`
* `int(value)`: convert `value` to an int. Value can be a number or a string representation of a number
* `float(value)`: convert `value` to a floating point number
* `str(value)`: convert `value` to a string
* `timedelta_to_seconds(time_delta)`: convert a TimeDelta object into seconds. This is useful for getting the number of seconds between two dates.
  * e.g. `timedelta_to_seconds(time_end - time_start)`
* `range(start, [stop], [skip])`: the same as the python [`range` function](https://docs.python.org/2/library/functions.html#range). Note that for performance reasons this is limited to 100 items or less.

#### "Month Start Date" and "Month End Date" expressions

`month_start_date` returns date of first day in the month of given date and `month_end_date` returns date of last day in the month of given date.

The `date_expression` can be any valid expression, or simply constant

```json
{
    "type": "month_start_date",
    "date_expression": {
        "type": "property_name",
        "property_name": "dob",
    },
}
```


#### Filter, Sort, Map and Reduce Expressions

We have following expressions that act on a list of objects or list of lists. The list to operate on is specified by `items_expression`. This can be any valid expression that returns a list. If the `items_expression` doesn't return a valid list, these might either fail or return one of empty list or `None` value.

##### map_items Expression

`map_items` performs a calculation specified by `map_expression` on each item of the list specified by `items_expression` and returns a list of the calculation results. The `map_expression` is evaluated relative to each item in the list and not relative to the parent document from which the list is specified. For e.g. if `items_expression` is a path to repeat-list of children in a form document, `map_expression` is a path relative to the repeat item.

`items_expression` can be any valid expression that returns a list. If this doesn't evaluate to a list an empty list is returned.

`map_expression` can be any valid expression relative to the items in above list.

```json
{
    "type": "map_items",
    "items_expression": {
        "type": "property_path",
        "property_path": ["form", "child_repeat"]
    },
    "map_expression": {
        "type": "property_path",
        "property_path": ["age"]
    }
}
```
Above returns list of ages. Note that the `property_path` in `map_expression` is relative to the repeat item rather than to the form.


##### filter_items Expression

`filter_items` performs filtering on given list and returns a new list. If the boolean expression specified by `filter_expression` evaluates to a `True` value, the item is included in the new list and if not, is not included in the new list.

`items_expression` can be any valid expression that returns a list. If this doesn't evaluate to a list an empty list is returned.

`filter_expression` can be any valid boolean expression relative to the items in above list.

```json
{
    "type": "filter_items",
    "items_expression": {
        "type": "property_name",
        "property_name": "family_repeat"
    },
    "filter_expression": {
       "type": "boolean_expression",
        "expression": {
            "type": "property_name",
            "property_name": "gender"
        },
        "operator": "eq",
        "property_value": "female"
    }
}
```

##### sort_items Expression

`sort_items` returns a sorted list of items based on sort value of each item.The sort value of an item is specified by `sort_expression`. By default, list will be in ascending order. Order can be changed by adding optional `order` expression with one of `DESC` (for descending) or `ASC` (for ascending) If a sort-value of an item is `None`, the item will appear in the start of list. If sort-values of any two items can't be compared, an empty list is returned.

`items_expression` can be any valid expression that returns a list. If this doesn't evaluate to a list an empty list is returned.

`sort_expression` can be any valid expression relative to the items in above list, that returns a value to be used as sort value.

```json
{
    "type": "sort_items",
    "items_expression": {
        "type": "property_path",
        "property_path": ["form", "child_repeat"]
    },
    "sort_expression": {
        "type": "property_path",
        "property_path": ["age"]
    }
}
```

##### reduce_items Expression

`reduce_items` returns aggregate value of the list specified by `aggregation_fn`.

`items_expression` can be any valid expression that returns a list. If this doesn't evaluate to a list, `aggregation_fn` will be applied on an empty list

`aggregation_fn` is one of following supported functions names.


Function Name  | Example
-------------- | -----------
`count`        | `['a', 'b']` -> 2
`sum`          | `[1, 2, 4]` -> 7
`min`          | `[2, 5, 1]` -> 1
`max`          | `[2, 5, 1]` -> 5
`first_item`   | `['a', 'b']` -> 'a'
`last_item`    | `['a', 'b']` -> 'b'

```json
{
    "type": "reduce_items",
    "items_expression": {
        "type": "property_name",
        "property_name": "family_repeat"
    },
    "aggregation_fn": "count"
}
```
This returns number of family members

##### flatten_items expression

`flatten_items` takes list of list of objects specified by `items_expression` and returns one list of all objects.

`items_expression` is any valid expression that returns a list of lists. It this doesn't evaluate to a list of lists an empty list is returned.
```json
{
    "type": "flatten_items",
    "items_expression": {},
}
```


#### Named Expressions

Last, but certainly not least, are named expressions.
These are special expressions that can be defined once in a data source and then used throughout other filters and indicators in that data source.
This allows you to write out a very complicated expression a single time, but still use it in multiple places with a simple syntax.

Named expressions are defined in a special section of the data source. To reference a named expression, you just specify the type of `"named"` and the name as follows:

```json
{
    "type": "named",
    "name": "my_expression"
}
```

This assumes that your named expression section of your data source includes a snippet like the following:

```json
{
    "my_expression": {
        "type": "property_name",
        "property_name": "test"
    }
}
```

This is just a simple example - the value that `"my_expression"` takes on can be as complicated as you want _as long as it doesn't reference any other named expressions_.

### Boolean Expression Filters

A `boolean_expression` filter combines an *expression*, an *operator*, and a *property value* (a constant), to produce a statement that is either `True` or `False`. *Note: in the future the constant value may be replaced with a second expression to be more general, however currently only constant property values are supported.*

Here is a sample JSON format for simple `boolean_expression` filter:
```
{
    "type": "boolean_expression",
    "expression": {
        "type": "property_name",
        "property_name": "age",
        "datatype": "integer"
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
                "datatype": "integer"
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
                "datatype": "integer",
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

See [examples.md](examples/examples.md) for some practical examples showing various filter types.


## Indicators

Now that we know how to filter the data in our data source, we are still left with a very important problem: *how do we know what data to save*? This is where indicators come in. Indicators are the data outputs - what gets computed and put in a column in the database.

A typical data source will include many indicators (data that will later be included in the report). This section will focus on defining a single indicator. Single indicators can then be combined in a list to fully define a data source.

The overall set of possible indicators is theoretically any function that can take in a single document (form or case) and output a value. However the set of indicators that are configurable is more limited than that.

### Indicator Properties

All indicator definitions have the following properties:

Property        | Description
--------------- | -----------
type            | A specified type for the indicator. It must be one of the types listed below.
column_id       | The database column where the indicator will be saved.
display_name    | A display name for the indicator (not widely used, currently).

Additionally, specific indicator types have other type-specific properties. These are covered below.

### Indicator types

The following primary indicator types are supported:

Indicator Type  | Description
--------------  | -----------
boolean         | Save `1` if a filter is true, otherwise `0`.
expression      | Save the output of an expression.
choice_list     | Save multiple columns, one for each of a predefined set of choices
ledger_balances | Save a column for each product specified, containing ledger data

*Note/todo: there are also other supported formats, but they are just shortcuts around the functionality of these ones they are left out of the current docs.*

#### Boolean indicators

Now we see again the power of our filter framework defined above! Boolean indicators take any arbitrarily complicated filter expression and save a `1` to the database if the expression is true, otherwise a `0`.  Here is an example boolean indicator which will save `1` if a form has a question with ID `is_pregnant` with a value of `"yes"`:

```
{
    "type": "boolean",
    "column_id": "col",
    "filter": {
	    "type": "boolean_expression",
	    "expression": {
	        "type": "property_path",
	        "property_path": ["form", "is_pregnant"],
	    },
	    "operator": "eq",
	    "property_value": "yes"
	}
}
```

#### Expression indicators

Similar to the boolean indicators - expression indicators leverage the expression structure defined above to create arbitrarily complex indicators. Expressions can store arbitrary values from documents (as opposed to boolean indicators which just store `0`'s and `1`'s). Because of this they require a few additional properties in the definition:

Property        | Description
--------------- | -----------
datatype        | The datatype of the indicator. Current valid choices are: "date", "datetime", "string", "decimal", and "integer".
is_nullable     | Whether the database column should allow null values.
is_primary_key  | Whether the database column should be (part of?) the primary key. (TODO: this needs to be confirmed)
expression      | Any expression.
transform       | (optional) transform to be applied to the result of the expression. (see "Report Columns > Transforms" section below)

Here is a sample expression indicator that just saves the "age" property to an integer column in the database:

```
{
    "type": "expression",
    "expression": {
        "type": "property_name",
        "property_name": "age"
    },
    "column_id": "age",
    "datatype": "integer",
    "display_name": "age of patient"
}
```

#### Choice list indicators

Choice list indicators take a single choice column (select or multiselect) and expand it into multiple columns where each column represents a different choice. These can support both single-select and multi-select quesitons.

A sample spec is below:

```
{
    "type": "choice_list",
    "column_id": "col",
    "display_name": "the category",
    "property_name": "category",
    "choices": [
        "bug",
        "feature",
        "app",
        "schedule"
    ],
    "select_style": "single"
}
```

#### Ledger Balance Indicators

Ledger Balance indicators take a list of product codes and a ledger section,
and produce a column for each product code, saving the value found in the
corresponding ledger.

Property            | Description
--------------------|------------
ledger_section      | The ledger section to use for this indicator, for example, "stock"
product_codes       | A list of the products to include in the indicator.  This will be used in conjunction with the `column_id` to produce each column name.
case_id_expression  | (optional) An expression used to get the case where each ledger is found.  If not specified, it will use the row's doc id.

```
{
    "type": "ledger_balances",
    "column_id": "soh",
    "display_name": "Stock On Hand",
    "ledger_section": "stock",
    "product_codes": ["aspirin", "bandaids", "gauze"],
    "case_id_expression": {
        "type": "property_name",
        "property_name": "_id"
    }
}
```

This spec would produce the following columns in the data source:

soh_aspirin | soh_bandaids | soh_gauze
------------|--------------|----------
 20         |  11          |  5
 67         |  32          |  9


### Practical notes for creating indicators

These are some practical notes for how to choose what indicators to create.

#### Fractions

All indicators output single values. Though fractional indicators are common, these should be modeled as two separate indicators (for numerator and denominator) and the relationship should be handled in the report UI config layer.

## Saving Multiple Rows per Case/Form

You can save multiple rows per case/form by specifying a root level `base_item_expression` that describes how to get the repeat data from the main document.
You can also use the `root_doc` expression type to reference parent properties
and the `base_iteration_number` expression type to reference the current index of the item.
This can be combined with the `iterator` expression type to do complex data source transforms.
This is not described in detail, but the following sample (which creates a table off of a repeat element called "time_logs" can be used as a guide).
There are also additional examples in the [examples](examples/examples.md):

```
{
    "domain": "user-reports",
    "doc_type": "DataSourceConfiguration",
    "referenced_doc_type": "XFormInstance",
    "table_id": "sample-repeat",
    "display_name": "Time Logged",
    "base_item_expression": {
        "type": "property_path",
        "property_path": ["form", "time_logs"]
    },
    "configured_filter": {
    },
    "configured_indicators": [
        {
            "type": "expression",
            "expression": {
                "type": "property_name",
                "property_name": "start_time"
            },
            "column_id": "start_time",
            "datatype": "datetime",
            "display_name": "start time"
        },
        {
            "type": "expression",
            "expression": {
                "type": "property_name",
                "property_name": "end_time"
            },
            "column_id": "end_time",
            "datatype": "datetime",
            "display_name": "end time"
        },
        {
            "type": "expression",
            "expression": {
                "type": "property_name",
                "property_name": "person"
            },
            "column_id": "person",
            "datatype": "string",
            "display_name": "person"
        },
        {
            "type": "expression",
            "expression": {
                "type": "root_doc",
                "expression": {
                    "type": "property_name",
                    "property_name": "name"
                }
            },
            "column_id": "name",
            "datatype": "string",
            "display_name": "name of ticket"
        }
    ]
}
```

# Report Configurations

A report configuration takes data from a data source and renders it in the UI. A report configuration consists of a few different sections:

1. [Report Filters](#report-filters) - These map to filters that show up in the UI, and should translate to queries that can be made to limit the returned data.
2. [Aggregation](#aggregation) - This defines what each row of the report will be. It is a list of columns forming the *primary key* of each row.
3. [Report Columns](#report-columns) - Columns define the report columns that show up from the data source, as well as any aggregation information needed.
4. [Charts](#charts) - Definition of charts to display on the report.
5. [Sort Expression](#sort-expression) - How the rows in the report are ordered.

## Samples

Here are some sample configurations that can be used as a reference until we have better documentation.

- [Dimagi chart report](https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/userreports/examples/dimagi/dimagi-chart-report.json)
- [GSID form report](https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/userreports/examples/gsid/gsid-form-report.json)


## Report Filters

The documentation for report filters is still in progress. Apologies for brevity below.

**A note about report filters versus data source filters**

Report filters are _completely_ different from data source filters. Data source filters limit the global set of data that ends up in the table, whereas report filters allow you to select values to limit the data returned by a query.

### Numeric Filters
Numeric filters allow users to filter the rows in the report by comparing a column to some constant that the user specifies when viewing the report.
Numeric filters are only intended to be used with numeric (integer or decimal type) columns. Supported operators are =, &ne;, &lt;, &le;, &gt;, and &ge;.

ex:
```
{
  "type": "numeric",
  "slug": "number_of_children_slug",
  "field": "number_of_children",
  "display": "Number of Children"
}
```

### Date filters

Date filters allow you filter on a date. They will show a datepicker in the UI.

```
{
  "type": "date",
  "slug": "modified_on",
  "field": "modified_on",
  "display": "Modified on",
  "required": false
}
```
Date filters have an optional `compare_as_string` option that allows the date
filter to be compared against an indicator of data type `string`. You shouldn't
ever need to use this option (make your column a `date` or `datetime` type
instead), but it exists because the report builder needs it.

### Quarter filters

Quarter filters are similar to date filters, but a choice is restricted only to the particular quarter of the year. They will show inputs for year and quarter in the UI.

```
{
  "type": "quarter",
  "slug": "modified_on",
  "field": "modified_on",
  "display": "Modified on",
  "required": false
}
```

### Pre-Filters

Pre-filters offer the kind of functionality you get from
[data source filters](#data-source-filtering). This makes it easier to use one
data source for many reports, especially if some of those reports just need
the data source to be filtered slightly differently. Pre-filters do not need
to be configured by app builders in report modules; fields with pre-filters
will not be listed in the report module among the other fields that can be
filtered.

A pre-filter's `type` is set to "pre":
```
{
  "type": "pre",
  "field": "at_risk_field",
  "slug": "at_risk_slug",
  "datatype": "string",
  "pre_value": "yes"
}
```

If `pre_value` is scalar (i.e. `datatype` is "string", "integer", etc.), the
filter will use the "equals" operator. If `pre_value` is null, the filter will
use "is null". If `pre_value` is an array, the filter will use the "in"
operator. e.g.
```
{
  "type": "pre",
  "field": "at_risk_field",
  "slug": "at_risk_slug",
  "datatype": "array",
  "pre_value": ["yes", "maybe"]
}
```

(If `pre_value` is an array and `datatype` is not "array", it is assumed that
`datatype` refers to the data type of the items in the array.)

### Dynamic choice lists

Dynamic choice lists provide a select widget that will generate a list of options dynamically.

The default behavior is simply to show all possible values for a column, however you can also specify a `choice_provider` to customize this behavior (see below).

Simple example assuming "village" is a name:
```json
{
  "type": "dynamic_choice_list",
  "slug": "village",
  "field": "village",
  "display": "Village",
  "datatype": "string"
}
```

#### Choice providers

Currently the supported `choice_provider`s are supported:


Field                | Description
-------------------- | -----------
location             | Select a location by name
user                 | Select a user
owner                | Select a possible case owner owner (user, group, or location)


Location choice providers also support two additional configuration options:

* "include_descendants" - Include descendant locations in the results. Defaults to `false`.
* "show_full_path" - display the full path to the location in the filter.  Defaults to `false`.

Example assuming "village" is a location ID, which is converted to names using the location `choice_provider`:
```json
{
  "type": "dynamic_choice_list",
  "slug": "village",
  "field": "location_id",
  "display": "Village",
  "datatype": "string",
  "choice_provider": {
      "type": "location",
      "include_descendants": true,
      "show_full_path": true
  }
}
```

### Choice lists

Choice lists allow manual configuration of a fixed, specified number of choices and let you change what they look like in the UI.
```
{
  "type": "choice_list",
  "slug": "role",
  "field": "role",
  "choices": [
    {"value": "doctor", "display": "Doctor"},
    {"value": "nurse"}
  ]
}
```

### Internationalization

Report builders may specify translations for the filter display value.
Also see the sections on internationalization in the Report Column and
the [translations transform](#translations-and-arbitrary-mappings).

```json
{
    "type": "choice_list",
    "slug": "state",
    "display": {"en": "State", "fr": "État"},
    ...
}
```

## Report Columns

Reports are made up of columns. The currently supported column types ares:

* [_field_](#field-columns) which represents a single value
* [_percent_](#percent-columns) which combines two values in to a percent
* [_aggregate_date_](#aggregatedatecolumn) which aggregates data by month
* [_expanded_](#expanded-columns) which expands a select question into multiple columns

### Field columns

Field columns have a type of `"field"`. Here's an example field column that shows the owner name from an associated `owner_id`:

```json
{
    "type": "field",
    "field": "owner_id",
    "column_id": "owner_id",
    "display": "Owner Name",
    "format": "default",
    "transform": {
        "type": "custom",
        "custom_type": "owner_display"
    },
    "aggregation": "simple"
}
```

### Percent columns

Percent columns have a type of `"percent"`. They must specify a `numerator` and `denominator` as separate field columns. Here's an example percent column that shows the percentage of pregnant women who had danger signs.

```
{
  "type": "percent",
  "column_id": "pct_danger_signs",
  "display": "Percent with Danger Signs",
  "format": "both",
  "denominator": {
    "type": "field",
    "aggregation": "sum",
    "field": "is_pregnant",
    "column_id": "is_pregnant"
  },
  "numerator": {
    "type": "field",
    "aggregation": "sum",
    "field": "has_danger_signs",
    "column_id": "has_danger_signs"
  }
}
```

#### Formats

The following percentage formats are supported.

Format          | Description                                    | example
--------------- | -----------------------------------------------| --------
percent         | A whole number percentage (the default format) | 33%
fraction        | A fraction                                     | 1/3
both            | Percentage and fraction                        | 33% (1/3)
numeric_percent | Percentage as a number                         | 33
decimal         | Fraction as a decimal number                   | .333


### AggregateDateColumn

AggregateDate columns allow for aggregating data by month over a given date field.  They have a type of `"aggregate_date"`. Unlike regular fields, you do not specify how aggregation happens, it is automatically grouped by month.

Here's an example of an aggregate date column that aggregates the `received_on` property for each month (allowing you to count/sum things that happened in that month).

```json
 {
    "column_id": "received_on",
    "field": "received_on",
    "type": "aggregate_date",
    "display": "Month"
  }
```

AggregateDate supports an optional "format" parameter, which accepts the same [format string](https://docs.python.org/2/library/datetime.html#strftime-strptime-behavior) as [Date formatting](#date-formatting). If you don't specify a format, the default will be "%Y-%m", which will show as, for example, "2008-09".

Keep in mind that the only variables available for formatting are `year` and `month`, but that still gives you a fair range, e.g.

| format    | Example result    |
| --------- | ----------------- |
| "%Y-%m"   | "2008-09"         |
| "%B, %Y"  | "September, 2008" |
| "%b (%y)" | "Sep (08)"        |


### Expanded Columns

Expanded columns have a type of `"expanded"`. Expanded columns will be "expanded" into a new column for each distinct value in this column of the data source. For example:

If you have a data source like this:
```
+---------|----------|-------------+
| Patient | district | test_result |
+---------|----------|-------------+
| Joe     | North    | positive    |
| Bob     | North    | positive    |
| Fred    | South    | negative    |
+---------|----------|-------------+
```
and a report configuration like this:
```
aggregation columns:
["district"]

columns:
[
  {
    "type": "field",
    "field": "district",
    "column_id": "district",
    "format": "default",
    "aggregation": "simple"
  },
  {
    "type": "expanded",
    "field": "test_result",
    "column_id": "test_result",
    "format": "default"
  }
]
```
Then you will get a report like this:
```
+----------|----------------------|----------------------+
| district | test_result-positive | test_result-negative |
+----------|----------------------|----------------------+
| North    | 2                    | 0                    |
| South    | 0                    | 1                    |
+----------|----------------------|----------------------+
```

Expanded columns have an optional parameter `"max_expansion"` (defaults to 10) which limits the number of columns that can be created.  WARNING: Only override the default if you are confident that there will be no adverse performance implications for the server.

### Expression columns

Expression columns can be used to do just-in-time calculations on the data coming out of reports.
They allow you to use any UCR expression on the data in the report row.
These can be referenced according to the `column_id`s from the other defined column.
They can support advanced use cases like doing math on two different report columns,
or doing conditional logic based on the contents of another column.

A simple example is below, which assumes another called "number" in the report and shows
how you could make a column that is 10 times that column.


```json
{
    "type": "expression",
    "column_id": "by_tens",
    "display": "Counting by tens",
    "expression": {
        "type": "evaluator",
        "statement": "a * b",
        "context_variables": {
            "a": {
                "type": "property_name",
                "property_name": "number"
            },
            "b": 10
        }
    }
}
```

### The "aggregation" column property

The aggregation column property defines how the column should be aggregated. If the report is not doing any aggregation, or if the column is one of the aggregation columns this should always be `"simple"` (see [Aggregation](#aggregation) below for more information on aggregation).

The following table documents the other aggregation options, which can be used in aggregate reports.

Format          | Description
--------------- | -----------------------------------------------
simple          | No aggregation
avg             | Average (statistical mean) of the values
count_unique    | Count the unique values found
count           | Count all rows
min             | Choose the minimum value
max             | Choose the maximum value
sum             | Sum the values

#### Column IDs

Column IDs in percentage fields *must be unique for the whole report*. If you use a field in a normal column and in a percent column you must assign unique `column_id` values to it in order for the report to process both.


### Calculating Column Totals

To sum a column and include the result in a totals row at the bottom of the report, set the `calculate_total` value in the column configuration to `true`.

Not supported for the following column types:
- expression

### Internationalization
Report columns can be translated into multiple languages.
To translate values in a given column check out
the [translations transform](#translations-and-arbitrary-mappings) below.
To specify translations for a column header, use an object as the `display`
value in the configuration instead of a string. For example:
```
{
    "type": "field",
    "field": "owner_id",
    "column_id": "owner_id",
    "display": {
        "en": "Owner Name",
        "he": "שם"
    },
    "format": "default",
    "transform": {
        "type": "custom",
        "custom_type": "owner_display"
    },
    "aggregation": "simple"
}
```
The value displayed to the user is determined as follows:
- If a display value is specified for the users language, that value will appear in the report.
- If the users language is not present, display the `"en"` value.
- If `"en"` is not present, show an arbitrary translation from the `display` object.
- If `display` is a string, and not an object, the report shows the string.

Valid `display` languages are any of the two or three letter language codes available on the user settings page.


## Aggregation

Aggregation in reports is done using a list of columns to aggregate on.
This defines how indicator data will be aggregated into rows in the report.
The columns represent what will be grouped in the report, and should be the `column_id`s of valid report columns.
In most simple reports you will only have one level of aggregation. See examples below.

### No aggregation

Note that if you use `is_primary_key` in any of your columns, you must include all primary key columns here.

```json
["doc_id"]
```

### Aggregate by 'username' column

```json
["username"]
```

### Aggregate by two columns

```json
["column1", "column2"]
```

## Transforms

Transforms can be used in two places - either to manipulate the value of a column just before it gets saved to a data source, or to transform the value returned by a column just before it reaches the user in a report.
Here's an example of a transform used in a report config 'field' column:

```json
{
    "type": "field",
    "field": "owner_id",
    "column_id": "owner_id",
    "display": "Owner Name",
    "format": "default",
    "transform": {
        "type": "custom",
        "custom_type": "owner_display"
    },
    "aggregation": "simple"
}
```

The currently supported transform types are shown below:

### Translations and arbitrary mappings

The translations transform can be used to give human readable strings:

```json
{
    "type": "translation",
    "translations": {
        "lmp": "Last Menstrual Period",
        "edd": "Estimated Date of Delivery"
    }
}
```

And for translations:

```json
{
    "type": "translation",
    "translations": {
        "lmp": {
            "en": "Last Menstrual Period",
            "es": "Fecha Última Menstruación",
        },
        "edd": {
            "en": "Estimated Date of Delivery",
            "es": "Fecha Estimada de Parto",
        }
    }
}
```

To use this in a mobile ucr, set the `'mobile_or_web'` property to `'mobile'`

```json
{
    "type": "translation",
    "mobile_or_web": "mobile",
    "translations": {
        "lmp": "Last Menstrual Period",
        "edd": "Estimated Date of Delivery"
    }
}
```

### Displaying username instead of user ID

```json
{
    "type": "custom",
    "custom_type": "user_display"
}
```

### Displaying username minus @domain.commcarehq.org instead of user ID

```json
{
    "type": "custom",
    "custom_type": "user_without_domain_display"
}
```

### Displaying owner name instead of owner ID

```json
{
    "type": "custom",
    "custom_type": "owner_display"
}
```

### Displaying month name instead of month index

```json
{
    "type": "custom",
    "custom_type": "month_display"
}
```

### Rounding decimals

Rounds decimal and floating point numbers to two decimal places.

```json
{
    "type": "custom",
    "custom_type": "short_decimal_display"
}
```

### Generic number formatting

Rounds numbers using Python's [built in formatting](https://docs.python.org/2.7/library/string.html#string-formatting).

See below for a few simple examples. Read the docs for complex ones. The input to the format string will be a _number_ not a string.

If the format string is not valid or the input is not a number then the original input will be returned.


#### Round to the nearest whole number

```json
{
    "type": "number_format",
    "custom_type": "{0:.0f}"
}
```

#### Always round to 3 decimal places

```json
{
    "type": "number_format",
    "custom_type": "{0:.3f}"
}
```

### Date formatting
Formats dates with the given format string. See [here](https://docs.python.org/2/library/datetime.html#strftime-strptime-behavior) for an explanation of format string behavior.
If there is an error formatting the date, the transform is not applied to that value.
```json
{
   "type": "date_format", 
   "format": "%Y-%m-%d %H:%M"
}
```

## Charts

There are currently three types of charts supported. Pie charts, and two types of bar charts.

### Pie charts

A pie chart takes two inputs and makes a pie chart. Here are the inputs:


Field              | Description
------------------ | -----------------------------------------------
aggregation_column | The column you want to group - typically a column from a select question
value_column       | The column you want to sum - often just a count

Here's a sample spec:

```
{
    "type": "pie",
    "title": "Remote status",
    "aggregation_column": "remote",
    "value_column": "count"
}
```

### Aggregate multibar charts

An aggregate multibar chart is used to aggregate across two columns (typically both of which are select questions). It takes three inputs:

Field                 | Description
--------------------- | -----------------------------------------------
primary_aggregation   | The primary aggregation. These will be the x-axis on the chart.
secondary_aggregation | The secondary aggregation. These will be the slices of the bar (or individual bars in "grouped" format)
value_column          | The column you want to sum - often just a count

Here's a sample spec:

```
{
    "type": "multibar-aggregate",
    "title": "Applicants by type and location",
    "primary_aggregation": "remote",
    "secondary_aggregation": "applicant_type",
    "value_column": "count"
}
```

### Multibar charts

A multibar chart takes a single x-axis column (typically a user, date, or select question) and any number of y-axis columns (typically indicators or counts) and makes a bar chart from them.

Field          | Description
---------------| -----------------------------------------------
x_axis_column  | This will be the x-axis on the chart.
y_axis_columns | These are the columns to use for the secondary axis. These will be the slices of the bar (or individual bars in "grouped" format).

Here's a sample spec:

```
{
    "type": "multibar",
    "title": "HIV Mismatch by Clinic",
    "x_axis_column": "clinic",
    "y_axis_columns": [
        {
            "column_id": "diagnoses_match_no",
            "display": "No match"
        },
        {
            "column_id": "diagnoses_match_yes",
            "display": "Match"
        }
    ]
}
```

## Sort Expression

A sort order for the report rows can be specified. Multiple fields, in either ascending or descending order, may be specified. Example:

Field should refer to report column IDs, not database fields.

```
[
  {
    "field": "district", 
    "order": "DESC"
  }, 
  {
    "field": "date_of_data_collection", 
    "order": "ASC"
  }
]
```

# Mobile UCR

Mobile UCR is a beta feature that enables you to make application modules and charts linked to UCRs on mobile.
It also allows you to send down UCR data from a report as a fixture which can be used in standard case lists and forms throughout the mobile application.

The documentation for Mobile UCR is very sparse right now.

## Filters

On mobile UCR, filters can be automatically applied to the mobile reports based on hardcoded or user-specific data, or can be displayed to the user.

The documentation of mobile UCR filters is incomplete. However some are documented below.

### Custom Calendar Month

When configuring a report within a module, you can filter a date field by the 'CustomMonthFilter'.  The choice includes the following options:
- Start of Month (a number between 1 and 28)
- Period (a number between 0 and n with 0 representing the current month). 

Each custom calendar month will be "Start of the Month" to ("Start of the Month" - 1).  For example, if the start of the month is set to 21, then the period will be the 21th of the month -> 20th of the next month. 

Examples:
Assume it was May 15:
Period 0, day 21, you would sync April 21-May 15th
Period 1, day 21, you would sync March 21-April 20th
Period 2, day 21, you would sync February 21 -March 20th

Assume it was May 20:
Period 0, day 21, you would sync April 21-May 20th
Period 1, day 21, you would sync March 21-April 20th
Period 2, day 21, you would sync February 21-March 20th

Assume it was May 21:
Period 0, day 21, you would sync May 21-May 21th
Period 1, day 21, you would sync April 21-May 20th
Period 2, day 21, you would sync March 21-April 20th

# Export

A UCR data source can be exported, to back an excel dashboard, for instance.
The URL for exporting data takes the form https://www.commcarehq.org/a/[domain]/configurable_reports/data_sources/export/[data source id]/
The export supports a "$format" parameter which can be any of the following options: html, csv, xlsx, xls.
The default format is csv.

This export can also be filtered to restrict the results returned.
The filtering options are all based on the field names:


URL parameter          | Value          | Description
-----------------------|----------------|-----------------------------
{field_name}           | {exact value}  | require an exact match
{field_name}-range     | {start}..{end} | return results in range
{field_name}-lastndays | {number}       | restrict to the last n days

This is configured in `export_data_source` and tested in `test_export`.  It
should be pretty straightforward to add support for additional filter types.

### Export example

Let's say you want to restrict the results to only cases owned by a particular
user, opened in the last 90 days, and with a child between 12 and 24 months old as an xlsx file.
The querystring might look like this:
```
?$format=xlsx&owner_id=48l069n24myxk08hl563&opened_on-lastndays=90&child_age-range=12..24
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

## Static data sources

As well as being able to define data sources via the UI which are stored in the database you
can also define static data sources which live as JSON documents in the source repository.

These are mainly useful for custom reports.

They conform to a slightly different style:
```
{
    "domains": ["live-domain", "test-domain"],
    "config": {
        ... put the normal data source configuration here
    }
}
```

Having defined the data source you need to add the path to the data source file to the `STATIC_DATA_SOURCES`
setting in `settings.py`. Now when the static data source pillow is run it will pick up the data source
and rebuild it.

Changes to the data source require restarting the pillow which will rebuild the SQL table. Alternately you
can use the UI to rebuild the data source (requires Celery to be running).


## Static configurable reports

Configurable reports can also be defined in the source repository.  Static configurable reports have
the following style:
```
{
    "domains": ["my-domain"],
    "data_source_table": "my_table",
    "report_id": "my-report",
    "config": {
        ... put the normal report configuration here
    }
}
```

## Custom configurable reports

Sometimes a client's needs for a rendered report are outside of the scope of the framework.  To render
the report using a custom Django template or with custom Excel formatting, define a subclass of
`ConfigurableReport` and override the necessary functions.  Then include the python path to the class
in the field `custom_configurable_report` of the static report and don't forget to include the static
report in `STATIC_DATA_SOURCES` in `settings.py`.

## Extending User Configurable Reports

When building a custom report for a client, you may find that you want to extend
UCR with custom functionality. The UCR framework allows developers to write
custom expressions, and register them with the framework. To do so, simply add
a tuple to the `CUSTOM_UCR_EXPRESSIONS` setting list. The first item in the tuple
is the name of the expression type, the second item is the path to a function
with a signature like conditional_expression(spec, context) that returns an
expression object. e.g.:

```
# settings.py

CUSTOM_UCR_EXPRESSIONS = [
    ('abt_supervisor', 'custom.abt.reports.expressions.abt_supervisor'),
]
```

Following are some custom expressions that are currently available.

- `location_type_name`:  A way to get location type from a location document id.
- `location_parent_id`:  A shortcut to get a location's parent ID a location id.
- `get_case_forms`: A way to get a list of forms submitted for a case.
- `get_subcases`: A way to get a list of subcases (child cases) for a case.

You can find examples of these in [practical examples](examples/examples.md).

## Inspecting database tables


The easiest way to inspect the database tables is to use the sql command line utility.
This can be done by runnning `./manage.py dbshell` or using `psql`.
The naming convention for tables is: `configurable_indicators_[domain name]_[table id]_[hash]`.
In postgres, you can see all tables by typing `\dt` and use sql commands to inspect the appropriate tables.
