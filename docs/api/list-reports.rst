List Reports 
============

Overview
--------

**Purpose**
    This endpoint provides a list of reports built in CommCare. This information can be used in the `Download Report Data API <download-report-data.rst>`_  to run a specific report and get the results.

**Base URL**

.. code-block:: text

    https://www.commcarehq.org/a/[PROJECT]/api/v0.5/simplereportconfiguration/?format=json

**HTTP Method**
    GET

Request & Response Details
---------------------------

**Output Details**

An array of the reports defined in the project. Each entry includes:

- **Columns**

  - A list of columns in the report. Each column has a type:

    - **"field"**: A single field column.
    - **"expanded"**: Expands into multiple result columns when downloading report data.

- **Filters**

  The filters that can be used for the report.

  - The filters can have a datatype that is *"string"*, *"integer"*, or *"decimal"*.
  - The type of the filter can be *"date"*, *"choice_list"*, or *"dynamic_choice_list"*.

    - Choice lists contain a set of predefined choices displayed to the user. These can be treated as strings when querying the reports.

**Sample JSON Output**

.. code-block:: json

    [
      {
        "columns": [
          {
            "column_id": "name",
            "display": "Name",
            "type": "field"
          },
          {
            "column_id": "gender",
            "display": "Gender",
            "type": "expanded"
          },
          {
            "column_id": "address",
            "display": "Person Address",
            "type": "field"
          }
        ],
        "filters": [
          {
            "datatype": "string",
            "slug": "closed"
          },
          {
            "datatype": "string",
            "slug": "owner_name"
          }
        ],
        "title": "Test Report 1",
        "id": "9aab0eeb88555a7b3bc8676883e7379a",
        "resource_uri": "/a/[PROJECT]/api/v0.5/simplereportconfiguration/9aab0eeb88555a7b3bc8676883e7379a/"
      },
      {
        "columns": [
          {
            "column_id": "district",
            "display": "District",
            "type": "field"
          },
          {
            "column_id": "number_of_children_visited",
            "display": "Num Children Visited",
            "type": "field"
          },
          {
            "column_id": "number_of_children_underweight",
            "display": "Underweight",
            "type": "field"
          }
        ],
        "filters": [
          {
            "datatype": "string",
            "slug": "closed"
          },
          {
            "datatype": "string",
            "slug": "owner_name"
          },
          {
            "datatype": "integer",
            "slug": "child_age"
          },
          {
            "datatype": "date",
            "slug": "form_date"
          }
        ],
        "title": "Test Report 2",
        "id": "9aab0eeb88555a7b4568676883e7379a",
        "resource_uri": "/a/[PROJECT]/api/v0.5/simplereportconfiguration/9aab0eeb88555a7b4568676883e7379a/"
      }
    ]
