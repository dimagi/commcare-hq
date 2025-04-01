Download Report Data
====================

Overview
--------
**Purpose**
    This endpoint will allow you to download the results of running a report on CommCare. To identify the reports available, see `List Reports <list-reports.rst>`_ .

**Authentication**
    For more information, please review `API Authentication <https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2279637003/CommCare+API+Overview#API-Authentication>`_

**Base URL**

.. code-block:: text

    https://www.commcarehq.org/a/[PROJECT]/api/configurablereportdata/v1/REPORTID/

**Method**
    GET

**Permission Required**
    View Data

Request & Response Details
---------------------------

**Input Parameters**

The report data can be filtered (based on the report's filter) and is also paged.

.. list-table::
   :header-rows: 1

   * - Name
     - Description
     - Example
   * - ``offset``
     - The record number to start at. Default is 0.
     - ``offset=100``
   * - ``limit``
     - The maximum number of records to return. Maximum: 50
     - ``limit=50``
   * - ``filter_name``
     - Each report can be filtered by filters defined on the List Reports API. Each filter is optional and can provide values for multiple filters.
        - For date filters, you are required to provide "start" and "end" ranges (ex. form_date-start and form_date-end)
        - To filter on multiple values for a given filter use the %1F separator between the values.
        - For numeric types, its possible to filter on greater than / less than (i.e. age > 10). To do this, you need to provide an operator and an operand. For example, to filter on age, you can use age-operator=>&age-operand=10. Valid operators are >= <= = != < >.
     - ``state=vermont%1Fnewyork&gender=male&form_date-start=2015-01-01&form_date-end=2015-02-01&age-operator=>&age-operand=10``

**Sample Usage**

.. code-block:: text

    https://www.commcarehq.org/a/[PROJECT]/api/configurablereportdata/v1/9aab0eeb88555a7b4568676883e7379a/?offset=20&limit=10&state=vermont&gender=male

**Sample JSON Output**

.. code-block:: json

    {
      "columns": [
        {
          "header": "District",
          "slug": "district"
        },
        {
          "header": "Num Children Visited",
          "slug": "number_of_children_visited"
        },
        {
          "header": "Gender-male",
          "expand_column_value": "male",
          "slug": "gender-male"
        },
        {
          "header": "Gender-female",
          "expand_column_value": "female",
          "slug": "gender-female"
        }
      ],
      "data": [
        {
          "district": "Middlesex",
          "number_of_children_visited": 46,
          "gender-male": 10,
          "gender-female": 35
        },
        {
          "district": "Suffolk",
          "number_of_children_visited": 85,
          "gender-male": 81,
          "gender-female": 4
        }
      ],
      "next_page": "/a/[PROJECT]/api/configurablereportdata/v1/9aab0eeb88555a7b4568676883e7379a/?offset=3&limit=3&state=vermont",
      "total_records": 30
    }

If the column type is **"expanded"**, there may be multiple results for a given column - these are named ``column_id-0``, ``column_id-1``, etc. Each result represents a unique value of that column. The **headers** section includes details on the value of each column.
