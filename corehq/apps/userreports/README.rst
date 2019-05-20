User Configurable Reporting
***************************

An overview of the design, API and data structures used here.

.. contents::
   :local:

Data Flow
=========

Reporting is handled in multiple stages. Here is the basic workflow.

Raw data (form or case) → [Data source config] → Row in database table →
[Report config] → Report in HQ

Both the data source config and report config are JSON documents that
live in the database. The data source config determines how raw data
(forms and cases) gets mapped to rows in an intermediary table, while
the report config(s) determine how that report table gets turned into an
interactive report in the UI.

Data Sources
============

Each data source configuration maps a filtered set of the raw data to
indicators. A data source configuration consists of two primary
sections:

1. A filter that determines whether the data is relevant for the data
   source
2. A list of indicators in that data source

In addition to these properties there are a number of relatively
self-explanatory fields on a data source such as the ``table_id`` and
``display_name``, and a few more nuanced ones. The full list of
available fields is summarized in the following table:

+---------------------------------------------+------------------------+
| Field                                       | Description            |
+=============================================+========================+
| filter                                      | Determines whether the |
|                                             | data is relevant for   |
|                                             | the data source        |
+---------------------------------------------+------------------------+
| indicators                                  | List of indicators to  |
|                                             | save                   |
+---------------------------------------------+------------------------+
| table_id                                    | A unique ID for the    |
|                                             | table                  |
+---------------------------------------------+------------------------+
| display_name                                | A display name for the |
|                                             | table that shows up in |
|                                             | UIs                    |
+---------------------------------------------+------------------------+
| base_item_expression                        | Used for making tables |
|                                             | off of repeat or list  |
|                                             | data                   |
+---------------------------------------------+------------------------+
| named_expressions                           | A list of named        |
|                                             | expressions that can   |
|                                             | be referenced in other |
|                                             | filters and indicators |
+---------------------------------------------+------------------------+
| named_filters                               | A list of named        |
|                                             | filters that can be    |
|                                             | referenced in other    |
|                                             | filters and indicators |
+---------------------------------------------+------------------------+

Data Source Filtering
---------------------

When setting up a data source configuration, filtering defines what data
applies to a given set of indicators. Some example uses of filtering on
a data source include:

-  Restricting the data by document type (e.g. cases or forms). This is
   a built-in filter.
-  Limiting the data to a particular case or form type
-  Excluding demo user data
-  Excluding closed cases
-  Only showing data that meets a domain-specific condition
   (e.g. pregnancy cases opened for women over 30 years of age)

Filter type overview
~~~~~~~~~~~~~~~~~~~~

There are currently four supported filter types. However, these can be
used together to produce arbitrarily complicated expressions.

+--------------------+--------------------------------------------------+
| Filter Type        | Description                                      |
+====================+==================================================+
| boolean_expression | A expression / logic statement (more below)      |
+--------------------+--------------------------------------------------+
| and                | An "and" of other filters - true if all are true |
+--------------------+--------------------------------------------------+
| or                 | An "or" of other filters - true if any are true  |
+--------------------+--------------------------------------------------+
| not                | A "not" or inverse expression on a filter        |
+--------------------+--------------------------------------------------+

To understand the ``boolean_expression`` type, we must first explain
expressions.

Expressions
~~~~~~~~~~~

An *expression* is a way of representing a set of operations that should
return a single value. Expressions can basically be thought of as
functions that take in a document and return a value:

*Expression*: ``function(document) → value``

In normal math/python notation, the following are all valid expressions
on a ``doc`` (which is presumed to be a ``dict`` object:

-  ``"hello"``
-  ``7``
-  ``doc["name"]``
-  ``doc["child"]["age"]``
-  ``doc["age"] < 21``
-  ``"legal" if doc["age"] > 21 else "underage"``

In user configurable reports the following expression types are
currently supported (note that this can and likely will be extended in
the future):

+-------------------------------+-------------------------+------------+
| Expression Type               | Description             | Example    |
+===============================+=========================+============+
| identity                      | Just returns whatever   | ``doc``    |
|                               | is passed in            |            |
+-------------------------------+-------------------------+------------+
| constant                      | A constant              | ``"hello"` |
|                               |                         | `,         |
|                               |                         | ``4``,     |
|                               |                         | ``2014-12- |
|                               |                         | 20``       |
+-------------------------------+-------------------------+------------+
| property_name                 | A reference to the      | ``doc["nam |
|                               | property in a document  | e"]``      |
+-------------------------------+-------------------------+------------+
| property_path                 | A nested reference to a | ``doc["chi |
|                               | property in a document  | ld"]["age" |
|                               |                         | ]``        |
+-------------------------------+-------------------------+------------+
| conditional                   | An if/else expression   | ``"legal"  |
|                               |                         | if doc["ag |
|                               |                         | e"] > 21 e |
|                               |                         | lse "under |
|                               |                         | age"``     |
+-------------------------------+-------------------------+------------+
| switch                        | A switch statement      | ``if doc[" |
|                               |                         | age"] == 2 |
|                               |                         | 1: "legal" |
|                               |                         | ``         |
|                               |                         | ``elif doc |
|                               |                         | ["age"] == |
|                               |                         |  60: ...`` |
|                               |                         | ``else: .. |
|                               |                         | .``        |
+-------------------------------+-------------------------+------------+
| array_index                   | An index into an array  | ``doc[1]`` |
+-------------------------------+-------------------------+------------+
| split_string                  | Splitting a string and  | ``doc["foo |
|                               | grabbing a specific     |  bar"].spl |
|                               | element from it by      | it(' ')[0] |
|                               | index                   | ``         |
+-------------------------------+-------------------------+------------+
| iterator                      | Combine multiple        | ``[doc.nam |
|                               | expressions into a list | e, doc.age |
|                               |                         | , doc.gend |
|                               |                         | er]``      |
+-------------------------------+-------------------------+------------+
| related_doc                   | A way to reference      | ``form.cas |
|                               | something in another    | e.owner_id |
|                               | document                | ``         |
+-------------------------------+-------------------------+------------+
| root_doc                      | A way to reference the  | ``repeat.p |
|                               | root document           | arent.name |
|                               | explicitly (only needed | ``         |
|                               | when making a data      |            |
|                               | source from             |            |
|                               | repeat/child data)      |            |
+-------------------------------+-------------------------+------------+
| ancestor_location             | A way to retrieve the   |            |
|                               | ancestor of a           |            |
|                               | particular type from a  |            |
|                               | location                |            |
+-------------------------------+-------------------------+------------+
| nested                        | A way to chain any two  | ``f1(f2(do |
|                               | expressions together    | c))``      |
+-------------------------------+-------------------------+------------+
| dict                          | A way to emit a         | ``{"name": |
|                               | dictionary of key/value |  "test", " |
|                               | pairs                   | value": f( |
|                               |                         | doc)}``    |
+-------------------------------+-------------------------+------------+
| add_days                      | A way to add days to a  | ``my_date  |
|                               | date                    | + timedelt |
|                               |                         | a(days=15) |
|                               |                         | ``         |
+-------------------------------+-------------------------+------------+
| add_months                    | A way to add months to  | ``my_date  |
|                               | a date                  | + relative |
|                               |                         | delta(mont |
|                               |                         | hs=15)``   |
+-------------------------------+-------------------------+------------+
| month_start_date              | First day in the month  | ``2015-01- |
|                               | of a date               | 20``       |
|                               |                         | ->         |
|                               |                         | ``2015-01- |
|                               |                         | 01``       |
+-------------------------------+-------------------------+------------+
| month_end_date                | Last day in the month   | ``2015-01- |
|                               | of a date               | 20``       |
|                               |                         | ->         |
|                               |                         | ``2015-01- |
|                               |                         | 31``       |
+-------------------------------+-------------------------+------------+
| diff_days                     | A way to get duration   | ``(to_date |
|                               | in days between two     |  - from-da |
|                               | dates                   | te).days`` |
+-------------------------------+-------------------------+------------+
| evaluator                     | A way to do arithmetic  | ``a + b*c  |
|                               | operations              | / d``      |
+-------------------------------+-------------------------+------------+
| base_iteration_number         | Used with               | ``loop.ind |
|                               | ```base_item_expression | ex``       |
|                               | `` <#saving-multiple-ro |            |
|                               | ws-per-caseform>`__     |            |
|                               | - a way to get the      |            |
|                               | current iteration       |            |
|                               | number (starting from   |            |
|                               | 0).                     |            |
+-------------------------------+-------------------------+------------+

Following expressions act on a list of objects or a list of lists (for
e.g. on a repeat list) and return another list or value. These
expressions can be combined to do complex aggregations on list data.

+-------------------------------+-------------------------+------------+
| Expression Type               | Description             | Example    |
+===============================+=========================+============+
| filter_items                  | Filter a list of items  | ``[1, 2, 3 |
|                               | to make a new list      | , -1, -2,  |
|                               |                         | -3] -> [1, |
|                               |                         |  2, 3]``   |
|                               |                         | (filter    |
|                               |                         | numbers    |
|                               |                         | greater    |
|                               |                         | than zero) |
+-------------------------------+-------------------------+------------+
| map_items                     | Map one list to another | ``[{'name' |
|                               | list                    | : 'a', gen |
|                               |                         | der: 'f'}, |
|                               |                         |  {'name':  |
|                               |                         | 'b, gender |
|                               |                         | : 'm'}]``  |
|                               |                         | ->         |
|                               |                         | ``['a', 'b |
|                               |                         | ']``       |
|                               |                         | (list of   |
|                               |                         | names from |
|                               |                         | list of    |
|                               |                         | child      |
|                               |                         | data)      |
+-------------------------------+-------------------------+------------+
| sort_items                    | Sort a list based on an | ``[{'name' |
|                               | expression              | : 'a', age |
|                               |                         | : 5}, {'na |
|                               |                         | me': 'b, a |
|                               |                         | ge: 3}]``  |
|                               |                         | ->         |
|                               |                         | ``[{'name' |
|                               |                         | : 'b, age: |
|                               |                         |  3}, {'nam |
|                               |                         | e': 'a', a |
|                               |                         | ge: 5}]``  |
|                               |                         | (sort      |
|                               |                         | child data |
|                               |                         | by age)    |
+-------------------------------+-------------------------+------------+
| reduce_items                  | Aggregate a list of     | sum on     |
|                               | items into one value    | ``[1, 2, 3 |
|                               |                         | ]``        |
|                               |                         | -> ``6``   |
+-------------------------------+-------------------------+------------+
| flatten                       | Flatten multiple lists  | ``[[1, 2], |
|                               | of items into one list  |  [4, 5]]`` |
|                               |                         | ->         |
|                               |                         | ``[1, 2, 4 |
|                               |                         | , 5]``     |
+-------------------------------+-------------------------+------------+

JSON snippets for expressions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Here are JSON snippets for the various expression types. Hopefully they
are self-explanatory.

Constant Expression
'''''''''''''''''''

.. autoclass:: corehq.apps.userreports.expressions.specs.ConstantGetterSpec

Property Name Expression
''''''''''''''''''''''''

.. autoclass:: corehq.apps.userreports.expressions.specs.PropertyNameGetterSpec

Property Path Expression
''''''''''''''''''''''''

.. autoclass:: corehq.apps.userreports.expressions.specs.PropertyPathGetterSpec

Conditional Expression
''''''''''''''''''''''

.. autoclass:: corehq.apps.userreports.expressions.specs.ConditionalExpressionSpec

Switch Expression
'''''''''''''''''

.. autoclass:: corehq.apps.userreports.expressions.specs.SwitchExpressionSpec

Coalesce Expression
'''''''''''''''''''

.. autoclass:: corehq.apps.userreports.expressions.specs.CoalesceExpressionSpec

Array Index Expression
''''''''''''''''''''''

.. autoclass:: corehq.apps.userreports.expressions.specs.ArrayIndexExpressionSpec

Split String Expression
'''''''''''''''''''''''

.. autoclass:: corehq.apps.userreports.expressions.specs.SplitStringExpressionSpec

Iterator Expression
'''''''''''''''''''

.. autoclass:: corehq.apps.userreports.expressions.specs.IteratorExpressionSpec

Base iteration number expressions
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: corehq.apps.userreports.expressions.specs.IterationNumberExpressionSpec

Related document expressions
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: corehq.apps.userreports.expressions.specs.RelatedDocExpressionSpec

Ancestor location expression
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: corehq.apps.locations.ucr_expressions.AncestorLocationExpression

Nested expressions
^^^^^^^^^^^^^^^^^^

.. autoclass:: corehq.apps.userreports.expressions.specs.NestedExpressionSpec

Dict expressions
^^^^^^^^^^^^^^^^

.. autoclass:: corehq.apps.userreports.expressions.specs.DictExpressionSpec

"Add Days" expressions
^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: corehq.apps.userreports.expressions.date_specs.AddDaysExpressionSpec


"Add Months" expressions
^^^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: corehq.apps.userreports.expressions.date_specs.AddMonthsExpressionSpec

"Diff Days" expressions
^^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: corehq.apps.userreports.expressions.date_specs.DiffDaysExpressionSpec

"Month Start Date" and "Month End Date" expressions
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: corehq.apps.userreports.expressions.date_specs.MonthStartDateExpressionSpec

"Evaluator" expression
^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: corehq.apps.userreports.expressions.specs.EvalExpressionSpec

‘Get Case Sharing Groups' expression
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: corehq.apps.userreports.expressions.specs.CaseSharingGroupsExpressionSpec

‘Get Reporting Groups' expression
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: corehq.apps.userreports.expressions.specs.ReportingGroupsExpressionSpec

Filter, Sort, Map and Reduce Expressions
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

We have following expressions that act on a list of objects or list of
lists. The list to operate on is specified by ``items_expression``. This
can be any valid expression that returns a list. If the
``items_expression`` doesn't return a valid list, these might either
fail or return one of empty list or ``None`` value.

map_items Expression
''''''''''''''''''''

.. autoclass:: corehq.apps.userreports.expressions.list_specs.MapItemsExpressionSpec

filter_items Expression
'''''''''''''''''''''''

.. autoclass:: corehq.apps.userreports.expressions.list_specs.FilterItemsExpressionSpec

sort_items Expression
'''''''''''''''''''''

.. autoclass:: corehq.apps.userreports.expressions.list_specs.SortItemsExpressionSpec

reduce_items Expression
'''''''''''''''''''''''

.. autoclass:: corehq.apps.userreports.expressions.list_specs.ReduceItemsExpressionSpec

flatten expression
''''''''''''''''''

.. autoclass:: corehq.apps.userreports.expressions.list_specs.FlattenExpressionSpec

Named Expressions
^^^^^^^^^^^^^^^^^

.. autoclass:: corehq.apps.userreports.expressions.specs.NamedExpressionSpec

Boolean Expression Filters
~~~~~~~~~~~~~~~~~~~~~~~~~~

A ``boolean_expression`` filter combines an *expression*, an *operator*,
and a *property value* (a constant), to produce a statement that is
either ``True`` or ``False``. *Note: in the future the constant value
may be replaced with a second expression to be more general, however
currently only constant property values are supported.*

Here is a sample JSON format for simple ``boolean_expression`` filter:

::

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

This is equivalent to the python statement: ``doc["age"] > 21``

Operators
^^^^^^^^^

The following operators are currently supported:

+-----------------+-------------------+-----------------+------------+
| Operator        | Description       | Value type      | Example    |
+=================+===================+=================+============+
| ``eq``          | is equal          | constant        | ``doc["age |
|                 |                   |                 | "] == 21`` |
+-----------------+-------------------+-----------------+------------+
| ``not_eq``      | is not equal      | constant        | ``doc["age |
|                 |                   |                 | "] != 21`` |
+-----------------+-------------------+-----------------+------------+
| ``in``          | single value is   | list            | ``doc["col |
|                 | in a list         |                 | or"] in [" |
|                 |                   |                 | red", "blu |
|                 |                   |                 | e"]``      |
+-----------------+-------------------+-----------------+------------+
| ``in_multi``    | a value is in a   | list            | ``selected |
|                 | multi select      |                 | (doc["colo |
|                 |                   |                 | r"], "red" |
|                 |                   |                 | )``        |
+-----------------+-------------------+-----------------+------------+
| ``any_in_multi` | one of a list of  | list            | ``selected |
| `               | values in in a    |                 | (doc["colo |
|                 | multiselect       |                 | r"], ["red |
|                 |                   |                 | ", "blue"] |
|                 |                   |                 | )``        |
+-----------------+-------------------+-----------------+------------+
| ``lt``          | is less than      | number          | ``doc["age |
|                 |                   |                 | "] < 21``  |
+-----------------+-------------------+-----------------+------------+
| ``lte``         | is less than or   | number          | ``doc["age |
|                 | equal             |                 | "] <= 21`` |
+-----------------+-------------------+-----------------+------------+
| ``gt``          | is greater than   | number          | ``doc["age |
|                 |                   |                 | "] > 21``  |
+-----------------+-------------------+-----------------+------------+
| ``gte``         | is greater than   | number          | ``doc["age |
|                 | or equal          |                 | "] >= 21`` |
+-----------------+-------------------+-----------------+------------+

Compound filters
~~~~~~~~~~~~~~~~

Compound filters build on top of ``boolean_expression`` filters to
create boolean logic. These can be combined to support arbitrarily
complicated boolean logic on data. There are three types of filters,
*and*, *or*, and *not* filters. The JSON representation of these is
below. Hopefully these are self explanatory.

"And" Filters
^^^^^^^^^^^^^

The following filter represents the statement:
``doc["age"] < 21 and doc["nationality"] == "american"``:

::

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

"Or" Filters
^^^^^^^^^^^^

The following filter represents the statement:
``doc["age"] > 21 or doc["nationality"] == "european"``:

::

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

"Not" Filters
^^^^^^^^^^^^^

The following filter represents the statement:
``!(doc["nationality"] == "european")``:

::

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

*Note that this could be represented more simply using a single filter
with the ``not_eq`` operator, but "not" filters can represent more
complex logic than operators generally, since the filter itself can be
another compound filter.*

Practical Examples
~~~~~~~~~~~~~~~~~~

See `practical examples`_ for some practical examples
showing various filter types.

Indicators
----------

Now that we know how to filter the data in our data source, we are still
left with a very important problem: *how do we know what data to save*?
This is where indicators come in. Indicators are the data outputs - what
gets computed and put in a column in the database.

A typical data source will include many indicators (data that will later
be included in the report). This section will focus on defining a single
indicator. Single indicators can then be combined in a list to fully
define a data source.

The overall set of possible indicators is theoretically any function
that can take in a single document (form or case) and output a value.
However the set of indicators that are configurable is more limited than
that.

Indicator Properties
~~~~~~~~~~~~~~~~~~~~

All indicator definitions have the following properties:

+----------------------------------------+-----------------------------+
| Property                               | Description                 |
+========================================+=============================+
| type                                   | A specified type for the    |
|                                        | indicator. It must be one   |
|                                        | of the types listed below.  |
+----------------------------------------+-----------------------------+
| column_id                              | The database column where   |
|                                        | the indicator will be       |
|                                        | saved.                      |
+----------------------------------------+-----------------------------+
| display_name                           | A display name for the      |
|                                        | indicator (not widely used, |
|                                        | currently).                 |
+----------------------------------------+-----------------------------+
| comment                                | A string describing the     |
|                                        | indicator                   |
+----------------------------------------+-----------------------------+

Additionally, specific indicator types have other type-specific
properties. These are covered below.

Indicator types
~~~~~~~~~~~~~~~

The following primary indicator types are supported:

+---------------------------------------+------------------------------+
| Indicator Type                        | Description                  |
+=======================================+==============================+
| boolean                               | Save ``1`` if a filter is    |
|                                       | true, otherwise ``0``.       |
+---------------------------------------+------------------------------+
| expression                            | Save the output of an        |
|                                       | expression.                  |
+---------------------------------------+------------------------------+
| choice_list                           | Save multiple columns, one   |
|                                       | for each of a predefined set |
|                                       | of choices                   |
+---------------------------------------+------------------------------+
| ledger_balances                       | Save a column for each       |
|                                       | product specified,           |
|                                       | containing ledger data       |
+---------------------------------------+------------------------------+

*Note/todo: there are also other supported formats, but they are just
shortcuts around the functionality of these ones they are left out of
the current docs.*

Boolean indicators
^^^^^^^^^^^^^^^^^^

Now we see again the power of our filter framework defined above!
Boolean indicators take any arbitrarily complicated filter expression
and save a ``1`` to the database if the expression is true, otherwise a
``0``. Here is an example boolean indicator which will save ``1`` if a
form has a question with ID ``is_pregnant`` with a value of ``"yes"``:

::

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

Expression indicators
^^^^^^^^^^^^^^^^^^^^^

Similar to the boolean indicators - expression indicators leverage the
expression structure defined above to create arbitrarily complex
indicators. Expressions can store arbitrary values from documents (as
opposed to boolean indicators which just store ``0``\ 's and ``1``\ 's).
Because of this they require a few additional properties in the
definition:

+----------------------------------------+-----------------------------+
| Property                               | Description                 |
+========================================+=============================+
| datatype                               | The datatype of the         |
|                                        | indicator. Current valid    |
|                                        | choices are: "date",        |
|                                        | "datetime", "string",       |
|                                        | "decimal", "integer", and   |
|                                        | "small_integer".            |
+----------------------------------------+-----------------------------+
| is_nullable                            | Whether the database column |
|                                        | should allow null values.   |
+----------------------------------------+-----------------------------+
| is_primary_key                         | Whether the database column |
|                                        | should be (part of?) the    |
|                                        | primary key. (TODO: this    |
|                                        | needs to be confirmed)      |
+----------------------------------------+-----------------------------+
| create_index                           | Creates an index on this    |
|                                        | column. Only applicable if  |
|                                        | using the SQL backend       |
+----------------------------------------+-----------------------------+
| expression                             | Any expression.             |
+----------------------------------------+-----------------------------+
| transform                              | (optional) transform to be  |
|                                        | applied to the result of    |
|                                        | the expression. (see        |
|                                        | "Report Columns >           |
|                                        | Transforms" section below)  |
+----------------------------------------+-----------------------------+

Here is a sample expression indicator that just saves the "age" property
to an integer column in the database:

::

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

Choice list indicators
^^^^^^^^^^^^^^^^^^^^^^

Choice list indicators take a single choice column (select or
multiselect) and expand it into multiple columns where each column
represents a different choice. These can support both single-select and
multi-select quesitons.

A sample spec is below:

::

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

Ledger Balance Indicators
^^^^^^^^^^^^^^^^^^^^^^^^^

Ledger Balance indicators take a list of product codes and a ledger
section, and produce a column for each product code, saving the value
found in the corresponding ledger.

+--------------------------------------------+--------------------------+
| Property                                   | Description              |
+============================================+==========================+
| ledger_section                             | The ledger section to    |
|                                            | use for this indicator,  |
|                                            | for example, "stock"     |
+--------------------------------------------+--------------------------+
| product_codes                              | A list of the products   |
|                                            | to include in the        |
|                                            | indicator. This will be  |
|                                            | used in conjunction with |
|                                            | the ``column_id`` to     |
|                                            | produce each column      |
|                                            | name.                    |
+--------------------------------------------+--------------------------+
| case_id_expression                         | An expression used to    |
|                                            | get the case where each  |
|                                            | ledger is found. If not  |
|                                            | specified, it will use   |
|                                            | the row's doc id.        |
+--------------------------------------------+--------------------------+

::

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

This spec would produce the following columns in the data source:

+-------------+--------------+-----------+
| soh_aspirin | soh_bandaids | soh_gauze |
+=============+==============+===========+
| 20          | 11           | 5         |
+-------------+--------------+-----------+
| 67          | 32           | 9         |
+-------------+--------------+-----------+

If the ledger you're using is a due list and you wish to save the dates
instead of integers, you can change the "type" from "ledger_balances" to
"due_list_dates".

Practical notes for creating indicators
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

These are some practical notes for how to choose what indicators to
create.

Fractions
^^^^^^^^^

All indicators output single values. Though fractional indicators are
common, these should be modeled as two separate indicators (for
numerator and denominator) and the relationship should be handled in the
report UI config layer.

Saving Multiple Rows per Case/Form
----------------------------------

You can save multiple rows per case/form by specifying a root level
``base_item_expression`` that describes how to get the repeat data from
the main document. You can also use the ``root_doc`` expression type to
reference parent properties and the ``base_iteration_number`` expression
type to reference the current index of the item. This can be combined
with the ``iterator`` expression type to do complex data source
transforms. This is not described in detail, but the following sample
(which creates a table off of a repeat element called "time_logs" can be
used as a guide). There are also additional examples in the `practical examples`_:

::

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

Data Cleaning and Validation
----------------------------

Note this is only available for "static" data sources that are created in the HQ repository.

When creating a data source it can be valuable to have strict validation on the type of data that can be inserted.
The attribute ``validations`` at the top level of the configuration can use UCR expressions to determine if the data is invalid.
If an expression is deemed invalid, then the relevant error is stored in the ``InvalidUCRData`` model.

.. code:: json

   {
       "domain": "user-reports",
       "doc_type": "DataSourceConfiguration",
       "referenced_doc_type": "XFormInstance",
       "table_id": "sample-repeat",
       "base_item_expression": {},
       "validations": [{
            "name": "is_starred_valid",
            "error_message": "is_starred has unexpected value",
            "expression": {
                "type": "boolean_expression",
                "expression": {
                    "type": "property_name",
                    "property_name": "is_starred"
                },
                "operator": "in",
                "property_value": ["yes", "no"]
            }
       }],
       "configured_filter": {...},
       "configured_indicators": [...]
   }

Report Configurations
=====================

A report configuration takes data from a data source and renders it in
the UI. A report configuration consists of a few different sections:

1. `Report Filters <#report-filters>`__ - These map to filters that show
   up in the UI, and should translate to queries that can be made to
   limit the returned data.
2. `Aggregation <#aggregation>`__ - This defines what each row of the
   report will be. It is a list of columns forming the *primary key* of
   each row.
3. `Report Columns <#report-columns>`__ - Columns define the report
   columns that show up from the data source, as well as any aggregation
   information needed.
4. `Charts <#charts>`__ - Definition of charts to display on the report.
5. `Sort Expression <#sort-expression>`__ - How the rows in the report
   are ordered.

Samples
-------

Here are some sample configurations that can be used as a reference
until we have better documentation.

-  `Dimagi chart
   report <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/userreports/examples/dimagi/dimagi-chart-report.json>`__
-  `GSID form
   report <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/userreports/examples/gsid/gsid-form-report.json>`__

Report Filters
--------------

The documentation for report filters is still in progress. Apologies for
brevity below.

**A note about report filters versus data source filters**

Report filters are *completely* different from data source filters. Data
source filters limit the global set of data that ends up in the table,
whereas report filters allow you to select values to limit the data
returned by a query.

Numeric Filters
~~~~~~~~~~~~~~~

Numeric filters allow users to filter the rows in the report by
comparing a column to some constant that the user specifies when viewing
the report. Numeric filters are only intended to be used with numeric
(integer or decimal type) columns. Supported operators are =, ≠, <, ≤,
>, and ≥.

ex:

::

   {
     "type": "numeric",
     "slug": "number_of_children_slug",
     "field": "number_of_children",
     "display": "Number of Children"
   }

Date filters
~~~~~~~~~~~~

Date filters allow you filter on a date. They will show a datepicker in
the UI.

::

   {
     "type": "date",
     "slug": "modified_on",
     "field": "modified_on",
     "display": "Modified on",
     "required": false
   }

Date filters have an optional ``compare_as_string`` option that allows
the date filter to be compared against an indicator of data type
``string``. You shouldn't ever need to use this option (make your column
a ``date`` or ``datetime`` type instead), but it exists because the
report builder needs it.

Quarter filters
~~~~~~~~~~~~~~~

Quarter filters are similar to date filters, but a choice is restricted
only to the particular quarter of the year. They will show inputs for
year and quarter in the UI.

::

   {
     "type": "quarter",
     "slug": "modified_on",
     "field": "modified_on",
     "display": "Modified on",
     "required": false
   }

Pre-Filters
~~~~~~~~~~~

Pre-filters offer the kind of functionality you get from `data source
filters <#data-source-filtering>`__. This makes it easier to use one
data source for many reports, especially if some of those reports just
need the data source to be filtered slightly differently. Pre-filters do
not need to be configured by app builders in report modules; fields with
pre-filters will not be listed in the report module among the other
fields that can be filtered.

A pre-filter's ``type`` is set to "pre":

::

   {
     "type": "pre",
     "field": "at_risk_field",
     "slug": "at_risk_slug",
     "datatype": "string",
     "pre_value": "yes"
   }

If ``pre_value`` is scalar (i.e. ``datatype`` is "string", "integer",
etc.), the filter will use the "equals" operator. If ``pre_value`` is
null, the filter will use "is null". If ``pre_value`` is an array, the
filter will use the "in" operator. e.g.

::

   {
     "type": "pre",
     "field": "at_risk_field",
     "slug": "at_risk_slug",
     "datatype": "array",
     "pre_value": ["yes", "maybe"]
   }

(If ``pre_value`` is an array and ``datatype`` is not "array", it is
assumed that ``datatype`` refers to the data type of the items in the
array.)

You can optionally specify the operator that the prevalue filter uses by
adding a pre_operator argument. e.g.

::

   {
     "type": "pre",
     "field": "at_risk_field",
     "slug": "at_risk_slug",
     "datatype": "array",
     "pre_value": ["maybe", "yes"],
     "pre_operator": "between"
   }

Note that instead of using ``eq``, ``gt``, etc, you will need to use
``=``, ``>``, etc.

Dynamic choice lists
~~~~~~~~~~~~~~~~~~~~

Dynamic choice lists provide a select widget that will generate a list
of options dynamically.

The default behavior is simply to show all possible values for a column,
however you can also specify a ``choice_provider`` to customize this
behavior (see below).

Simple example assuming "village" is a name:

.. code:: json

   {
     "type": "dynamic_choice_list",
     "slug": "village",
     "field": "village",
     "display": "Village",
     "datatype": "string"
   }

Choice providers
^^^^^^^^^^^^^^^^

Currently the supported ``choice_provider``\ s are supported:

+----------+---------------------------------------------------------------+
| Field    | Description                                                   |
+==========+===============================================================+
| location | Select a location by name                                     |
+----------+---------------------------------------------------------------+
| user     | Select a user                                                 |
+----------+---------------------------------------------------------------+
| owner    | Select a possible case owner owner (user, group, or location) |
+----------+---------------------------------------------------------------+

Location choice providers also support three additional configuration
options:

-  "include_descendants" - Include descendants of the selected locations
   in the results. Defaults to ``false``.
-  "show_full_path" - Display the full path to the location in the
   filter. Defaults to ``false``. The default behavior shows all
   locations as a flat alphabetical list.
-  "location_type" - Includes locations of this type only. Default is to not
   filter on location type.

Example assuming "village" is a location ID, which is converted to names
using the location ``choice_provider``:

.. code:: json

   {
     "type": "dynamic_choice_list",
     "slug": "village",
     "field": "location_id",
     "display": "Village",
     "datatype": "string",
     "choice_provider": {
         "type": "location",
         "include_descendants": true,
         "show_full_path": true,
         "location_type": "district"
     }
   }

Choice lists
~~~~~~~~~~~~

Choice lists allow manual configuration of a fixed, specified number of
choices and let you change what they look like in the UI.

::

   {
     "type": "choice_list",
     "slug": "role",
     "field": "role",
     "choices": [
       {"value": "doctor", "display": "Doctor"},
       {"value": "nurse"}
     ]
   }

Drilldown by Location
~~~~~~~~~~~~~~~~~~~~~

This filter allows selection of a location for filtering by drilling
down from top level.

::

   {
     "type": "location_drilldown",
     "slug": "by_location",
     "field": "district_id",
     "include_descendants": true,
     "max_drilldown_levels": 3
   }

-  "include_descendants" - Include descendant locations in the results.
   Defaults to ``false``.
-  "max_drilldown_levels" - Maximum allowed drilldown levels. Defaults
   to 99

Internationalization
~~~~~~~~~~~~~~~~~~~~

Report builders may specify translations for the filter display value.
Also see the sections on internationalization in the Report Column and
the `translations transform <#translations-and-arbitrary-mappings>`__.

.. code:: json

   {
       "type": "choice_list",
       "slug": "state",
       "display": {"en": "State", "fr": "État"},
       ...
   }

Report Columns
--------------

Reports are made up of columns. The currently supported column types
ares:

-  `field <#field-columns>`__ which represents a single value
-  `percent <#percent-columns>`__ which combines two values in to a
   percent
-  `aggregate_date <#aggregatedatecolumn>`__ which aggregates data by
   month
-  `expanded <#expanded-columns>`__ which expands a select question into
   multiple columns
-  `expression <#expression-columns>`__ which can do calculations on
   data in other columns

Field columns
~~~~~~~~~~~~~

Field columns have a type of ``"field"``. Here's an example field column
that shows the owner name from an associated ``owner_id``:

.. code:: json

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

Percent columns
~~~~~~~~~~~~~~~

Percent columns have a type of ``"percent"``. They must specify a
``numerator`` and ``denominator`` as separate field columns. Here's an
example percent column that shows the percentage of pregnant women who
had danger signs.

::

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

Formats
^^^^^^^

The following percentage formats are supported.

+-----------------+------------------------------------------------+-----------+
| Format          | Description                                    | example   |
+=================+================================================+===========+
| percent         | A whole number percentage (the default format) | 33%       |
+-----------------+------------------------------------------------+-----------+
| fraction        | A fraction                                     | 1/3       |
+-----------------+------------------------------------------------+-----------+
| both            | Percentage and fraction                        | 33% (1/3) |
+-----------------+------------------------------------------------+-----------+
| numeric_percent | Percentage as a number                         | 33        |
+-----------------+------------------------------------------------+-----------+
| decimal         | Fraction as a decimal number                   | .333      |
+-----------------+------------------------------------------------+-----------+

AggregateDateColumn
~~~~~~~~~~~~~~~~~~~

AggregateDate columns allow for aggregating data by month over a given
date field. They have a type of ``"aggregate_date"``. Unlike regular
fields, you do not specify how aggregation happens, it is automatically
grouped by month.

Here's an example of an aggregate date column that aggregates the
``received_on`` property for each month (allowing you to count/sum
things that happened in that month).

.. code:: json

    {
       "column_id": "received_on",
       "field": "received_on",
       "type": "aggregate_date",
       "display": "Month"
     }

AggregateDate supports an optional "format" parameter, which accepts the
same `format
string <https://docs.python.org/2/library/datetime.html#strftime-strptime-behavior>`__
as `Date formatting <#date-formatting>`__. If you don't specify a
format, the default will be "%Y-%m", which will show as, for example,
"2008-09".

Keep in mind that the only variables available for formatting are
``year`` and ``month``, but that still gives you a fair range, e.g.

+-----------+-------------------+
| format    | Example result    |
+===========+===================+
| "%Y-%m"   | "2008-09"         |
+-----------+-------------------+
| "%B, %Y"  | "September, 2008" |
+-----------+-------------------+
| "%b (%y)" | "Sep (08)"        |
+-----------+-------------------+

ConditionalAggregationColumn
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**NOTE** This feature is only available to static UCR reports maintained
by Dimagi developers.

Conditional aggregation columns allow you to define a series of
conditional expressions with corresponding names, then group together
rows which which meet the same conditions. They have a type of
``"conditional_aggregation"``.

Here's an example that groups children based on their age at the time of
registration:

.. code:: json

   {
       "display": "age_range",
       "column_id": "age_range",
       "type": "conditional_aggregation",
       "whens": {
           "0 <= age_at_registration AND age_at_registration < 12": "infant",
           "12 <= age_at_registration AND age_at_registration < 36": "toddler",
           "36 <= age_at_registration AND age_at_registration < 60": "preschooler"
       },
       "else_": "older"
   }

The ``"whens"`` attribute maps conditional expressions to labels. If
none of the conditions are met, the row will receive the ``"else_"``
value, if provided.

Here's a more complex example which uses SQL functions to dynamically
calculate ranges based on a date property:

.. code:: json

   {
       "display": "Age Group",
       "column_id": "age_group",
       "type": "conditional_aggregation",
       "whens": {
           "extract(year from age(dob))*12 + extract(month from age(dob)) BETWEEN 0 and 5": "0_to_5",
           "extract(year from age(dob))*12 + extract(month from age(dob)) BETWEEN 6 and 11": "6_to_11",
           "extract(year from age(dob))*12 + extract(month from age(dob)) BETWEEN 12 and 35": "12_to_35",
           "extract(year from age(dob))*12 + extract(month from age(dob)) BETWEEN 36 and 59": "36_to_59",
           "extract(year from age(dob))*12 + extract(month from age(dob)) BETWEEN 60 and 71": "60_to_71"
       }
   }

Expanded Columns
~~~~~~~~~~~~~~~~

Expanded columns have a type of ``"expanded"``. Expanded columns will be
"expanded" into a new column for each distinct value in this column of
the data source. For example:

If you have a data source like this:

::

   +---------|----------|-------------+
   | Patient | district | test_result |
   +---------|----------|-------------+
   | Joe     | North    | positive    |
   | Bob     | North    | positive    |
   | Fred    | South    | negative    |
   +---------|----------|-------------+

and a report configuration like this:

::

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

Then you will get a report like this:

::

   +----------|----------------------|----------------------+
   | district | test_result-positive | test_result-negative |
   +----------|----------------------|----------------------+
   | North    | 2                    | 0                    |
   | South    | 0                    | 1                    |
   +----------|----------------------|----------------------+

Expanded columns have an optional parameter ``"max_expansion"``
(defaults to 10) which limits the number of columns that can be created.
WARNING: Only override the default if you are confident that there will
be no adverse performance implications for the server.

Expression columns
~~~~~~~~~~~~~~~~~~

Expression columns can be used to do just-in-time calculations on the
data coming out of reports. They allow you to use any UCR expression on
the data in the report row. These can be referenced according to the
``column_id``\ s from the other defined column. They can support
advanced use cases like doing math on two different report columns, or
doing conditional logic based on the contents of another column.

A simple example is below, which assumes another called "number" in the
report and shows how you could make a column that is 10 times that
column.

.. code:: json

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

The "aggregation" column property
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The aggregation column property defines how the column should be
aggregated. If the report is not doing any aggregation, or if the column
is one of the aggregation columns this should always be ``"simple"``
(see `Aggregation <#aggregation>`__ below for more information on
aggregation).

The following table documents the other aggregation options, which can
be used in aggregate reports.

+--------------+------------------------------------------+
| Format       | Description                              |
+==============+==========================================+
| simple       | No aggregation                           |
+--------------+------------------------------------------+
| avg          | Average (statistical mean) of the values |
+--------------+------------------------------------------+
| count_unique | Count the unique values found            |
+--------------+------------------------------------------+
| count        | Count all rows                           |
+--------------+------------------------------------------+
| min          | Choose the minimum value                 |
+--------------+------------------------------------------+
| max          | Choose the maximum value                 |
+--------------+------------------------------------------+
| sum          | Sum the values                           |
+--------------+------------------------------------------+

Column IDs
^^^^^^^^^^

Column IDs in percentage fields *must be unique for the whole report*.
If you use a field in a normal column and in a percent column you must
assign unique ``column_id`` values to it in order for the report to
process both.

Calculating Column Totals
~~~~~~~~~~~~~~~~~~~~~~~~~

To sum a column and include the result in a totals row at the bottom of
the report, set the ``calculate_total`` value in the column
configuration to ``true``.

Not supported for the following column types: - expression

.. _internationalization-1:

Internationalization
~~~~~~~~~~~~~~~~~~~~

Report columns can be translated into multiple languages. To translate
values in a given column check out the `translations
transform <#translations-and-arbitrary-mappings>`__ below. To specify
translations for a column header, use an object as the ``display`` value
in the configuration instead of a string. For example:

::

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

The value displayed to the user is determined as follows: - If a display
value is specified for the users language, that value will appear in the
report. - If the users language is not present, display the ``"en"``
value. - If ``"en"`` is not present, show an arbitrary translation from
the ``display`` object. - If ``display`` is a string, and not an object,
the report shows the string.

Valid ``display`` languages are any of the two or three letter language
codes available on the user settings page.

Aggregation
-----------

Aggregation in reports is done using a list of columns to aggregate on.
This defines how indicator data will be aggregated into rows in the
report. The columns represent what will be grouped in the report, and
should be the ``column_id``\ s of valid report columns. In most simple
reports you will only have one level of aggregation. See examples below.

No aggregation
~~~~~~~~~~~~~~

Note that if you use ``is_primary_key`` in any of your columns, you must
include all primary key columns here.

.. code:: json

   ["doc_id"]

Aggregate by ‘username' column
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: json

   ["username"]

Aggregate by two columns
~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: json

   ["column1", "column2"]

Transforms
----------

Transforms can be used in two places - either to manipulate the value of
a column just before it gets saved to a data source, or to transform the
value returned by a column just before it reaches the user in a report.
Here's an example of a transform used in a report config ‘field' column:

.. code:: json

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

The currently supported transform types are shown below:

Translations and arbitrary mappings
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The translations transform can be used to give human readable strings:

.. code:: json

   {
       "type": "translation",
       "translations": {
           "lmp": "Last Menstrual Period",
           "edd": "Estimated Date of Delivery"
       }
   }

And for translations:

.. code:: json

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

To use this in a mobile ucr, set the ``'mobile_or_web'`` property to
``'mobile'``

.. code:: json

   {
       "type": "translation",
       "mobile_or_web": "mobile",
       "translations": {
           "lmp": "Last Menstrual Period",
           "edd": "Estimated Date of Delivery"
       }
   }

Displaying username instead of user ID
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: json

   {
       "type": "custom",
       "custom_type": "user_display"
   }

Displaying username minus @domain.commcarehq.org instead of user ID
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: json

   {
       "type": "custom",
       "custom_type": "user_without_domain_display"
   }

Displaying owner name instead of owner ID
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: json

   {
       "type": "custom",
       "custom_type": "owner_display"
   }

Displaying month name instead of month index
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: json

   {
       "type": "custom",
       "custom_type": "month_display"
   }

Rounding decimals
~~~~~~~~~~~~~~~~~

Rounds decimal and floating point numbers to two decimal places.

.. code:: json

   {
       "type": "custom",
       "custom_type": "short_decimal_display"
   }

Generic number formatting
~~~~~~~~~~~~~~~~~~~~~~~~~

Rounds numbers using Python's `built in
formatting <https://docs.python.org/2.7/library/string.html#string-formatting>`__.

See below for a few simple examples. Read the docs for complex ones. The
input to the format string will be a *number* not a string.

If the format string is not valid or the input is not a number then the
original input will be returned.

Round to the nearest whole number
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code:: json

   {
       "type": "number_format",
       "format_string": "{0:.0f}"
   }

Always round to 3 decimal places
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code:: json

   {
       "type": "number_format",
       "format_string": "{0:.3f}"
   }

Date formatting
~~~~~~~~~~~~~~~

Formats dates with the given format string. See
`here <https://docs.python.org/2/library/datetime.html#strftime-strptime-behavior>`__
for an explanation of format string behavior. If there is an error
formatting the date, the transform is not applied to that value.

.. code:: json

   {
      "type": "date_format", 
      "format": "%Y-%m-%d %H:%M"
   }

Converting an ethiopian date string to a gregorian date
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Converts a string in the YYYY-MM-DD format to a gregorian date. For
example, 2009-09-11 is converted to date(2017, 5, 19). If it is unable
to convert the date, it will return an empty string.

.. code:: json

   {
      "type": "custom",
      "custom_type": "ethiopian_date_to_gregorian_date"
   }

Converting a gregorian date string to an ethiopian date
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Converts a string in the YYYY-MM-DD format to an ethiopian date. For
example, 2017-05-19 is converted to date(2009, 09, 11). If it is unable
to convert the date, it will return an empty string.

.. code:: json

   {
      "type": "custom",
      "custom_type": "gregorian_date_to_ethiopian_date"
   }

Charts
------

There are currently three types of charts supported. Pie charts, and two
types of bar charts.

Pie charts
~~~~~~~~~~

A pie chart takes two inputs and makes a pie chart. Here are the inputs:

+------------------+---------------------------------------------------+
| Field            | Description                                       |
+==================+===================================================+
| aggregation_colu | The column you want to group - typically a column |
| mn               | from a select question                            |
+------------------+---------------------------------------------------+
| value_column     | The column you want to sum - often just a count   |
+------------------+---------------------------------------------------+

Here's a sample spec:

::

   {
       "type": "pie",
       "title": "Remote status",
       "aggregation_column": "remote",
       "value_column": "count"
   }

Aggregate multibar charts
~~~~~~~~~~~~~~~~~~~~~~~~~

An aggregate multibar chart is used to aggregate across two columns
(typically both of which are select questions). It takes three inputs:

+---------------------+------------------------------------------------+
| Field               | Description                                    |
+=====================+================================================+
| primary_aggregation | The primary aggregation. These will be the     |
|                     | x-axis on the chart.                           |
+---------------------+------------------------------------------------+
| secondary_aggregati | The secondary aggregation. These will be the   |
| on                  | slices of the bar (or individual bars in       |
|                     | "grouped" format)                              |
+---------------------+------------------------------------------------+
| value_column        | The column you want to sum - often just a      |
|                     | count                                          |
+---------------------+------------------------------------------------+

Here's a sample spec:

::

   {
       "type": "multibar-aggregate",
       "title": "Applicants by type and location",
       "primary_aggregation": "remote",
       "secondary_aggregation": "applicant_type",
       "value_column": "count"
   }

Multibar charts
~~~~~~~~~~~~~~~

A multibar chart takes a single x-axis column (typically a user, date,
or select question) and any number of y-axis columns (typically
indicators or counts) and makes a bar chart from them.

+----------------+-----------------------------------------------------+
| Field          | Description                                         |
+================+=====================================================+
| x_axis_column  | This will be the x-axis on the chart.               |
+----------------+-----------------------------------------------------+
| y_axis_columns | These are the columns to use for the secondary      |
|                | axis. These will be the slices of the bar (or       |
|                | individual bars in "grouped" format).               |
+----------------+-----------------------------------------------------+

Here's a sample spec:

::

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

Sort Expression
---------------

A sort order for the report rows can be specified. Multiple fields, in
either ascending or descending order, may be specified. Example:

Field should refer to report column IDs, not database fields.

::

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

Mobile UCR
==========

Mobile UCR is a beta feature that enables you to make application
modules and charts linked to UCRs on mobile. It also allows you to send
down UCR data from a report as a fixture which can be used in standard
case lists and forms throughout the mobile application.

The documentation for Mobile UCR is very sparse right now.

Filters
-------

On mobile UCR, filters can be automatically applied to the mobile
reports based on hardcoded or user-specific data, or can be displayed to
the user.

The documentation of mobile UCR filters is incomplete. However some are
documented below.

Custom Calendar Month
~~~~~~~~~~~~~~~~~~~~~

When configuring a report within a module, you can filter a date field
by the ‘CustomMonthFilter'. The choice includes the following options: -
Start of Month (a number between 1 and 28) - Period (a number between 0
and n with 0 representing the current month).

Each custom calendar month will be "Start of the Month" to ("Start of
the Month" - 1). For example, if the start of the month is set to 21,
then the period will be the 21th of the month -> 20th of the next month.

Examples: Assume it was May 15: Period 0, day 21, you would sync April
21-May 15th Period 1, day 21, you would sync March 21-April 20th Period
2, day 21, you would sync February 21 -March 20th

Assume it was May 20: Period 0, day 21, you would sync April 21-May 20th
Period 1, day 21, you would sync March 21-April 20th Period 2, day 21,
you would sync February 21-March 20th

Assume it was May 21: Period 0, day 21, you would sync May 21-May 21th
Period 1, day 21, you would sync April 21-May 20th Period 2, day 21, you
would sync March 21-April 20th

Export
======

A UCR data source can be exported, to back an excel dashboard, for
instance. The URL for exporting data takes the form
https://www.commcarehq.org/a/[domain]/configurable_reports/data_sources/export/[data
source id]/ The export supports a "$format" parameter which can be any
of the following options: html, csv, xlsx, xls. The default format is
csv.

This export can also be filtered to restrict the results returned. The
filtering options are all based on the field names:

+------------------------+----------------+-----------------------------+
| URL parameter          | Value          | Description                 |
+========================+================+=============================+
| {field_name}           | {exact value}  | require an exact match      |
+------------------------+----------------+-----------------------------+
| {field_name}-range     | {start}..{end} | return results in range     |
+------------------------+----------------+-----------------------------+
| {field_name}-lastndays | {number}       | restrict to the last n days |
+------------------------+----------------+-----------------------------+

This is configured in ``export_data_source`` and tested in
``test_export``. It should be pretty straightforward to add support for
additional filter types.

Export example
~~~~~~~~~~~~~~

Let's say you want to restrict the results to only cases owned by a
particular user, opened in the last 90 days, and with a child between 12
and 24 months old as an xlsx file. The querystring might look like this:

::

   ?$format=xlsx&owner_id=48l069n24myxk08hl563&opened_on-lastndays=90&child_age-range=12..24

Practical Notes
===============

Some rough notes for working with user configurable reports.

Getting Started
---------------

The easiest way to get started is to start with sample data and reports.

First copy the dimagi domain to your developer machine. You only really
need forms, users, and cases:

::

   ./manage.py copy_domain https://<your_username>:<your_password>@commcarehq.cloudant.com/commcarehq dimagi --include=CommCareCase,XFormInstance,CommCareUser

Then load and rebuild the data table:

::

   ./manage.py load_spec corehq/apps/userreports/examples/dimagi/dimagi-case-data-source.json --rebuild

Then load the report:

::

   ./manage.py load_spec corehq/apps/userreports/examples/dimagi/dimagi-chart-report.json

Fire up a browser and you should see the new report in your domain. You
should also be able to navigate to the edit UI, or look at and edit the
example JSON files. There is a second example based off the "gsid"
domain as well using forms.

The tests are also a good source of documentation for the various filter
and indicator formats that are supported.

Static data sources
-------------------

As well as being able to define data sources via the UI which are stored
in the database you can also define static data sources which live as
JSON documents in the source repository.

These are mainly useful for custom reports.

They conform to a slightly different style:

::

   {
       "domains": ["live-domain", "test-domain"],
       "config": {
           ... put the normal data source configuration here
       }
   }

Having defined the data source you need to add the path to the data
source file to the ``STATIC_DATA_SOURCES`` setting in ``settings.py``.
Now when the static data source pillow is run it will pick up the data
source and rebuild it.

Changes to the data source require restarting the pillow which will
rebuild the SQL table. Alternately you can use the UI to rebuild the
data source (requires Celery to be running).

Static configurable reports
---------------------------

Configurable reports can also be defined in the source repository.
Static configurable reports have the following style:

::

   {
       "domains": ["my-domain"],
       "data_source_table": "my_table",
       "report_id": "my-report",
       "config": {
           ... put the normal report configuration here
       }
   }

Custom configurable reports
---------------------------

Sometimes a client's needs for a rendered report are outside of the
scope of the framework. To render the report using a custom Django
template or with custom Excel formatting, define a subclass of
``ConfigurableReportView`` and override the necessary functions. Then
include the python path to the class in the field
``custom_configurable_report`` of the static report and don't forget to
include the static report in ``STATIC_DATA_SOURCES`` in ``settings.py``.

Extending User Configurable Reports
-----------------------------------

When building a custom report for a client, you may find that you want
to extend UCR with custom functionality. The UCR framework allows
developers to write custom expressions, and register them with the
framework. To do so, simply add a tuple to the
``CUSTOM_UCR_EXPRESSIONS`` setting list. The first item in the tuple is
the name of the expression type, the second item is the path to a
function with a signature like conditional_expression(spec, context)
that returns an expression object. e.g.:

::

   # settings.py

   CUSTOM_UCR_EXPRESSIONS = [
       ('abt_supervisor', 'custom.abt.reports.expressions.abt_supervisor'),
   ]

Following are some custom expressions that are currently available.

-  ``location_type_name``: A way to get location type from a location
   document id.
-  ``location_parent_id``: A shortcut to get a location's parent ID a
   location id.
-  ``get_case_forms``: A way to get a list of forms submitted for a
   case.
-  ``get_subcases``: A way to get a list of subcases (child cases) for a
   case.
-  ``indexed_case``: A way to get an indexed case from another case.

You can find examples of these in `practical examples`_.

Scaling UCR
-----------

Profiling data sources
~~~~~~~~~~~~~~~~~~~~~~

You can use
``./manage.py profile_data_source <domain> <data source id> <doc id>``
to profile a datasource on a particular doc. It will give you
information such as functions that take the longest and number of
database queries it initiates.

Faster Reporting
~~~~~~~~~~~~~~~~

If reports are slow, then you can add ``create_index`` to the data
source to any columns that have filters applied to them.

Asynchronous Indicators
~~~~~~~~~~~~~~~~~~~~~~~

If you have an expensive data source and the changes come in faster than
the pillow can process them, you can specify ``asynchronous: true`` in
the data source. This flag puts the document id in an intermediary table
when a change happens which is later processed by a celery queue. If
multiple changes are submitted before this can be processed, a new entry
is not created, so it will be processed once. This moves the bottle neck
from kafka/pillows to celery.

The main benefit of this is that documents will be processed only once
even if many changes come in at a time. This makes this approach ideal
datasources that don't require ‘live' data or where the source documents
change very frequently.

It is also possible achieve greater parallelization than is currently
available via pillows since multiple Celery workers can process the
changes.

A diagram of this workflow can be found
`here <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/userreports/examples/async_indicator.png>`__

Inspecting database tables
--------------------------

The easiest way to inspect the database tables is to use the sql command
line utility.

This can be done by runnning ``./manage.py dbshell`` or using ``psql``.

The naming convention for tables is:
``config_report_[domain name]_[table id]_[hash]``.

In postgres, you can see all tables by typing ``\dt`` and use sql
commands to inspect the appropriate tables.

.. _practical examples: ./ucr/examples.html
