=================================
Case Search Query Language (CSQL)
=================================

Underpinning some of the advanced search capabilities of Case Search and Case List Explorer is the
Case Search Query Language. This page describes the syntax and capabilities of the language as well
as it's limitations.

.. contents::
   :local:

Syntax
======

* **Available operators**: ``and``, ``or`` , ``=``, ``!=``, ``<``, ``<=``, ``>``, ``>=``, ``(``,
  ``)``
* **Brackets**: can be used to group logic and make complex expressions
* **Dates**: dates can be filtered with format ``YYYY-MM-DD``. This must include the apostrophes
  around the date. The ``date()`` function may be used to validate a date value:
  ``date('2021-08-20')``

Examples::

    name = 'john' and age > 10

    region = 'london' and registration_date < '2019-12-01'

    (sex = 'm' and weight < 23) or (sex = 'f' and weight < 20)

    status = 'negative' and subcase-exists('host', @case_type = 'lab_result' and result = 'positive')


Supported Functions
===================

The following functions are supported:


``date``
--------

* **Behavior**: Will convert a string or a number value into an equivalent date. Will throw an error
  if the format of the string is wrong or an invalid date is passed.
* **Return**: Returns a date
* **Arguments**: The value to be converted (either a string in the format ``YYYY-MM-DD`` or a
  number). Numbers are interpreted as days since Jan 01 1970.
* **Usage**: ``date(value_to_convert)``

``today``
---------
* **Return**:  Returns the current date according in the timezone of the project space.
* **Arguments**: None
* **Usage**: ``today()``
* **Note**: When comparing the output of this function to a value with a date and a time by using
  the ``=`` operator, this function returns the current date at midnight. For example,
  ``last_modified=today()`` will look for an exact match between the date and time in
  ``last_modified`` and the current date exactly at midnight.

``not``
-------
* **Behavior**: Invert a boolean search expression
* **Arguments**: The expression to invert
* **Usage**: ``not(is_active = 0 and stock_level < 15)``

``starts-with``
---------------
* **Behavior**: Match cases where a multi-select case property value begins with the given argument
  value.
* **Arguments**:  Two arguments, the multi-select case property and the value to check.
* **Notes**:
    * This filter is case sensitive
    * Using this filter may impact the performance of your query
* **Usage**:
    * ``starts-with(social_security_num, "123")``
    * ``starts-with(timezone, "Africa/")``

``selected``
------------
* **Behavior**: Match cases where a multi-select case property contains the given value. The
  behavior of this function matches that of the ``selected-any`` function.
* **Return**: True if that particular value is present in the case property.  Otherwise False.
* **Arguments**:  Two arguments, the multi-select case property and the value to check.
* **Notes**:
    * If the 'value to check' contains spaces, each word will be considered independently as in
      ``select-any``
    * `See notes on how case properties are segmented <multiselect_>`_
* **Usage**:
    * ``selected(tests_performed, "testA")``
    * ``selected(tests_performed, "testA testB")``
        * This works the same as the 'selected-any' function. Best practice would be to use
          ``selected-any`` in this instance to make the intention clear.

``selected-any``
----------------
* **Behavior**: Match cases where a multi-select case property contains ANY of the values in the
  input provided
* **Arguments**: Two arguments, the multi-select case property and the values to check represented
  as a space separated string.
* **Notes**: `See notes on how case properties are segmented <multiselect_>`_
* **Usage**: ``selected-any(tests_performed, "testA testB testC")``

.. list-table:: Outcomes table for ``selected-any``
   :header-rows: 1

   * - Search term
     - Case Property Value
     - Search Result
     - Note
   * - value1
     - value2 **value1** value3
     - Match
     - Property contains all of the search terms
   * - value1 value2
     - **value2** value5 **value1** value3
     - Match
     - Property contains all of the search terms
   * - value1 value2
     - **value1** value3
     - Match
     - Property contains at least one of the search terms
   * - value1 value2
     - value3 value4
     - No Match
     - Property does not contain any of the search terms

``selected-all``
----------------

* **Behavior**: Match cases where a multi-select case property contains ALL of the values in the
  input provided
* **Arguments**: Two arguments, the multi-select case property and the values to check represented
  as a space separated string.
* **Notes**:
    * `See notes on how case properties are segmented <multiselect_>`_
* **Usage**: ``selected-all(tests_performed, "testA testB testC")``

.. list-table:: Outcomes table for ``selected-all``
   :header-rows: 1

   * - Search term
     - Case Property Value
     - Search Result
     - Note
   * - value1
     - value2 **value1** value3
     - Match
     - Property contains all of the search terms
   * - value1 value2
     - **value2** value5 **value1** value3
     - Match
     - Property contains all of the search terms
   * - value1 value2
     - **value1** value3
     - No match
     - Property does not contain ALL of the search terms

``within-distance``
-------------------
* **Requirements**: GPS case properties
* **Behavior**: Match cases within a certain geographic distance (as the crow flies) of the provided
  point
* **Return**: True if that case is within range, otherwise false
* **Arguments**:
    * ``property_name``: The GPS case property on the cases being searched
    * ``coordinates``: This can be the output of a "geopoint" receiver from a geocoder question
    * ``distance``: The distance from ``coordinates`` to search
    * ``unit``: The units for that distance. Options are: miles, yards, feet, inch, kilometers,
      meters, centimeters, millimeters, nauticalmiles
* **Usage**: ``within-distance(location, '42.4402967 -71.1453275', 30, 'miles')``

``fuzzy-match``
---------------
* **Behavior**: Determines if a given value is a fuzzy match for a given case property.
* **Return**: True if that particular value matches the case property.  Otherwise False.
* **Arguments**:  Two arguments: the case property and the value to check.
* **Usage**: ``fuzzy-match(first_name, "Sara")``

.. note::
   ``fuzzy-match`` is backed by Elasticsearch's `Fuzzy query`_, which uses `Levenshtein distance`_
   to gauge similarity. Parameters for searches are tuned in implementation to balance matching with
   performance, but to consider something a match it generally requires matching initial prefix and
   an edit distance based on the length of the string (longer strings can have more edits).

.. _Fuzzy Query: https://www.elastic.co/guide/en/elasticsearch/reference/8.11/query-dsl-fuzzy-query.html
.. _Levenshtein distance: https://en.wikipedia.org/wiki/Levenshtein_distance

``fuzzy-date``
---------------
* **Behavior**: Determines if a given date is a fuzzy match for a given case property.
* **Return**: True if that particular date or any of the generated permutations matches the case property.
  Otherwise False.
* **Arguments**:  Two arguments: the case property and the date to check.
* **Usage**: ``fuzzy-date(dob, "2012-12-03")``

.. note::
   ``fuzzy-date`` generates a list of dates that might be the result of a typo in the date like switching
   day and month field or reversing the digits in either day, month or the decade part of the year. Only
   combinations of these that are valid dates will be check against.

``phonetic-match``
------------------
* **Behavior**: Match cases if a given value "sounds like" (using `Soundex`_) the value of a given
  case property. (e.g. "Joolea" will match "Julia")
* **Return**: True if that particular value matches the case property. Otherwise False.
* **Arguments**:  Two arguments: the case property and the value to check.
* **Usage**: ``phonetic-match(first_name, "Julia")``

.. _Soundex: https://en.wikipedia.org/wiki/Soundex#American_Soundex

``match-all``
-------------
* **Behavior**: Matches ALL cases
* **Arguments**: No arguments
* **Usage**: ``match-all()``
* **Example**: ``match-all() and first_name = "Julia"``
    * Matches cases that have a property ``first_name`` equal to ``"Julia"``

``match-none``
--------------
* **Behavior**:  Matches no cases at all
* **Arguments**:  No arguments
* **Usage**: ``match-none()``
* **Example**: ``match-none() or first_name = "Julia"``
    * Matches cases that have a property ``first_name`` equal to ``"Julia"``


Filtering on related cases
==========================

CSQL includes utilities for searching against ancestor cases (such as parents) and subcases (such as children)

.. warning::
    When utilizing related cases function, be mindful that the *quantity of search results* and the
    *number of subcase or ancestor functions* in a single search are important factors. As the
    number of related case functions and search results increases, the time required to perform the
    search will also increase.

    Keep in mind that a higher number of search results will lead to longer execution times for the
    search query. The threshold is around 400K to 500K search results, after which a timeout error
    may occur. It is recommended to keep your search results well below this number for optimal
    performance.

    To manage the number of search results when incorporating subcase or ancestor functions in your
    search query, you can apply required fields in the search form. For instance, requiring users to
    search by both first and last name is more effective than just using the first name. Including
    more required fields in the search form is likely to reduce the number of search results
    returned.

Searches may be performed against ancestor cases (e.g. parent cases) using the ``/`` operator

.. code-block::

    # search for cases that have a 'parent' case that matches the filter 'age > 55'
    parent/age > 55

    # successive steps can be added to navigate further up the case hierarchy
    parent/parent/dod = ''

``ancestor-exists``
-------------------
* **Behavior**: Match cases that have an ancestor with the given relation that matches the ancestor
  filter expression.
* **Arguments**: Two arguments, the ancestor relationship (usually one of parent or host) and the
  ancestor filter expression.
* **Usage**:
    * ``ancestor-exists(parent/parent, city = 'SF')``
    * ``ancestor-exists(parent, food_included = 'yes' and ancestor-exists(parent, city!='' and
      selected(city, 'Boston')))``
* **Limitation**:
    * The arguments can't be a standalone function and must be a binary expression
        * This will *not* work: ``ancestor-exists(parent, selected(city, 'SF'))``
        * This will work:  ``ancestor-exists(parent, city != '' and selected(city, 'SF'))``
    * The ancestor filter expression may not include ``subcase-exists`` or ``subcase-count``

``subcase-exists``
------------------
* **Behavior**: Match cases that have a subcase with the given relation that matches the subcase
  filter expression.
* **Arguments**: Two arguments, the subcase relationship (usually one of 'parent' or 'host') and the
  subcase filter expression.
* **Usage**: ``subcase-exists('parent', lab_type = 'blood' and result = 1)``

``subcase-count``
-----------------
* **Behavior**: Match cases where the number of subcases matches the given expression.
* **Arguments**: Two arguments, the subcase relationship (usually one of 'parent' or 'host') and the
  subcase filter expression.
* **Usage**: ``subcase-count('parent', lab_type = 'blood' and result = 1) > 3``
    * The count function must be used in conjunction with a comparison operator. All operators are
      supported (``=``, ``!=``, ``<``, ``<=``, ``>``, ``>=``)

**Examples**

A very common implementation of ``subcase-exists`` search queries involves utilizing the user's
'search-input'. Please see an example of this configuration below.

.. code-block::

    if(count(instance("search-input:results")/input/field[@name = "clinic"]),
       concat('subcase-exists("parent", @case_type = "service" and current_status = "active" and central_registry = "yes" and clinic_case_id = "',
              instance("search-input:results")/input/field[@name = "clinic"],
              '")'),
       '@case_id != "c"')


.. _multiselect:

Multi-select case property searches
===================================
As shown above, the ``selected`` , ``selected-any``  and ``selected-all``  functions can be used to filter cases based on multi-select case properties.

A multi-select case property is a case property whose value contains multiple 'terms'. Each 'term' in the case property value is typically separated by a space.
tests_completed = 'math english physics'

The following table illustrates how a case property value is split up into component terms. Note that some characters are removed and other are used as separators.

.. list-table::
   :header-rows: 1

   * - Case property value
     - Searchable terms
     - Note
   * - Case property value
     - Searchable terms
     - Note
   * - word1 word2     word3
     - [word1, word2, word3]
     - Split on white space
   * - word1 word-two 9-8
     - [word1, word, two, 9, 8]
     - Split on '-'
   * - word1 word_2
     - [word1, word_2]
     - Not split on '_'
   * - word1 5.9 word.2
     - [word1, 5.9, word, 2]
     - Split on 'period' between 'letters' but not between
   * - 'word1' "word2" word3?!
     - [word1, word2, word3]
     - Quotes and punctuation are ignored
   * - 你好
     - [你, 好]
     - Supports unicode characters
   * - word1 🧀 🍌 word2
     - [word1, word2]
     - Emoji are ignored
   * - word's
     - [words, words]
     - Apostrophe are removed
   * - word"s
     - [word, s]
     - Split on double quote between letters
   * - word1\\nword2
     - [word1, word2]
     - Split on white space ("\n" is a newline)
   * - 12/2=6x1   4*5   98%  3^2
     - [12, 2, 6x1, 4, 5, 98, 3, 2]
     - Split on 'non-word' characters
   * - start<point<end
     - [start, point, end]
     - Split on 'non-word' characters
   * - you&me
     - [you, me]
     - Split on 'non-word' characters
   * - (w1) ( w2 ) [w3] [ w4 ] ( [ w5
     - [w1, w2, w3, w4, w5]
     - Non-word characters are removed
   * - word1,word2,word3
     - [word1, word2, word3]
     - Split on 'non-word' characters

The process of analyzing case property values and producing terms is performed by the `Elasticsearch
Standard Analyzer`_.

.. _Elasticsearch Standard Analyzer: https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-standard-analyzer.html


.. note::
    Note that the CommCare functions ``selected`` and ``selected-at`` do not follow this pattern.
    They only consider white space as the term separator and do not strip punctuation etc.


Example Query + Tips
====================

In case lists, Default Search Filters allow you to automatically filter the results first shown in
the list. When writing xpath query Default Search Filters, you construct a string which then gets
passed to Elasticsearch to be evaluated as CSQL. These two layers can make it more challenging to
write these expressions since it requires wrapping the CSQL components in quotation marks. When
values are pulled from instances such as casedb or the session, these have to be pulled directly
before being put into the string. Here we will explore an example to better illustrate this:

In this example, we have the **service** case type as an extension of the **client** case type. The
**service** represents that the **client** is receiving treatment at a particular clinic. We are
going to look for clients who have open service cases associated with a clinic that is a part of the
user’s set of clinics (as defined by a user property called clinic_case_ids). In other words, we are
trying to find client who are receiving treatment from one of the user’s clinics.

The ``_xpath_query`` in the Default Search Filter section of our client case type case list looks like this:

.. code-block::

    concat(
      'subcase-exists("parent", @case_type = "service" and @status != "closed" and selected(clinic_case_id,"',
      instance('casedb')/casedb/case[@case_type='commcare-user'][hq_user_id=instance('commcaresession')/session/context/userid]/clinic_case_ids,
      '"))'
    )

Note that the ``instance('casedb')`` part is not in quotes initially. This is since we need to
actually evaluate that to find its value first, not treat it as a string. However, quotes are then
supplied in the ``concat()`` to wrap that value such that it later is properly viewed as a string.

After applying the ``concat()``, here is what the string would look like:

.. code-block::

    'subcase-exists("parent", @case_type = "service" and @status != "closed" and selected(clinic_case_id,"228cdd5d-064b-40fa-8335-7d37761e82ce 3ba5b7a1-2c6f-4d1e-904e-24285344a819"))'

This is now suited to be evaluated by Elasticsearch since it consists of only CSQL-valid functions
from the list at the top of this page such as ``subcase-exists()`` and ``selected()``


Limitations
===========

* Comparison between case properties is not supported
    * e.g. ``activity_completion_date < opened_on``
* Math is not supported
    * e.g. ``age = 7+3 , dob = today() - 7``
