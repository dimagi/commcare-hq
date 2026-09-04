Fixture Data APIs (or Lookup Tables)
====================================

Overview
--------

**Purpose**
    Retrieve all data associated with a fixture. See `this definition <https://github.com/dimagi/commcare-core/wiki/fixtures>`_.

Endpoint Specifications
-----------------------

**Base URLs**

- **For individual fixture items:**

  .. code-block:: text

      https://www.commcarehq.org/a/[domain]/api/fixture/v1/[fixture_item_id]/

- **For a specific fixture table:**

  .. code-block:: text

      https://www.commcarehq.org/a/[domain]/api/fixture/v1/?fixture_type=[name of table]

- **For a list of all fixture types:**

  .. code-block:: text

      https://www.commcarehq.org/a/[domain]/api/fixture/v1/

**Authentication**
    For more information, please review `API Authentication <https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2279637003/CommCare+API+Overview#API-Authentication>`_.

**Permission Required**
    Edit Apps

Request & Response Details
---------------------------

**Input Parameters (for the list of all fixtures):**

.. list-table::
   :header-rows: 1

   * - Name
     - Description
     - Example
   * - fixture_type
     - Returns the fixtures in a given domain whose data_type matches the specified type.
     - fixture_type=city

**Output Values:**

.. list-table::
   :header-rows: 1

   * - Name
     - Description
     - Example
   * - id
     - Fixture UUID
     - 1J9NF7B4FTH73435PYJJSL5SJ
   * - fixture_type
     - Name of the fixture's data_type
     - city
   * - fields
     - Values for the custom fields in the fixture.
     - {"name": "Boston", "population": 617594, "state": "Massachusetts"}

.. note::

    A call to the Fixture List API endpoint will return a JSON list of objects with these output values.
    In order to get the full table via API, use the 'name of the table', which is the same as you would find without the API call from https://www.commcarehq.org/a/[domain]/fixtures (the string in the Table ID column)


**Sample Input**

.. code-block:: text

    https://www.commcarehq.org/a/demo/api/fixture/v1/1J9NF7B4FTH73435PYJJSL5SJ/

**Sample Output**

.. code-block:: json

    {
        "fields": {
            "name": "Boston",
            "population": 617594,
            "state": "Massachusetts"
        },
        "fixture_type": "city",
        "resource_uri": "",
        "id": "1J9NF7B4FTH73435PYJJSL5SJ"
    }

Bulk Upload Lookup Tables
=========================

Overview
---------

**Purpose**
    Create or edit lookup tables by uploading an Excel file containing table data.

Endpoint Specifications
-----------------------
**URL**

.. code-block:: text

    https://www.commcarehq.org/a/[domain]/fixtures/fixapi/

**Method**
    POST

**Authorization**
    Basic Authorization

**Permission Required**
    Edit Apps

Request & Response Details
---------------------------

**Input Parameters**

.. list-table::
   :header-rows: 1

   * - Name
     - Description
     - Example
   * - file-to-upload
     - Path to the Excel file containing table data
     - /home/username/fixtures.xlsx
   * - replace
     - True if the existing tables should be deleted, otherwise False
     - false
   * - async
     - If true, the upload will be queued and processed in the background. A status URL will be provided to view progress
     - false

**Sample cURL Request**

.. code-block:: text

    curl -v https://www.commcarehq.org/a/myproject/fixtures/fixapi/ -u user@domain.com:password \
         -F "file-to-upload=@fixtures.xlsx" \
         -F "replace=true"

(You may also omit the ':' and password, and curl will request it. This will have the benefit of not showing your password on your screen or storing it in your history.)

**Response**

JSON output with the following parameters.

.. list-table::
   :header-rows: 1

   * - Name
     - Description
     - Example
   * - code
     - 200: Success
       402: Warning
       405: Fail
     - 402
   * - message
     - Warning or failure message
     - "Error processing your file. Submit a valid (.xlsx) file"
   * - status_url
     - URL for the progress of the lookup table upload (Only applicable when async=true)
     - https://www.commcarehq.org/a/demo/fixtures/fixapi/status/dl-2998e6834a654ab5ba74f372246caa75/

Lookup Table Individual API
============================

Manage lookup tables (the tables themselves, not their rows) via API calls.

.. openapi:: spec/lookup-table-v1.json

Lookup Table Rows API (v1)
===========================

Manage the rows of a lookup table via API calls.

.. openapi:: spec/lookup-table-item-v1.json

Lookup Table Rows API (v2)
===========================

Version 2 of the lookup table rows API returns the created or updated row in
the response body for write requests.

.. openapi:: spec/lookup-table-item-v2.json
