Fixture Data APIs (or Lookup Tables)
------------------------------------

**Purpose:**
    Retrieve all data associated with a fixture. See `this definition <https://github.com/dimagi/commcare-core/wiki/fixtures>`_.

**Authentication:**
    For more information, please review Authentication.

**Base URLs:**

- **For individual fixture items:**

  .. code-block:: text

      https://www.commcarehq.org/a/[domain]/api/[version]/fixture/[fixture_item_id]/

- **For a specific fixture table:**

  .. code-block:: text

      https://www.commcarehq.org/a/[domain]/api/[version]/fixture/?fixture_type=[name of table]

- **For a list of all fixture types:**

  .. code-block:: text

      https://www.commcarehq.org/a/[domain]/api/[version]/fixture/

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

**Note:** A call to the Fixture List API endpoint will return a JSON list of objects with these output values.

To get the full table via API, use the 'name of the table', which is the same as found without an API call from:

.. code-block:: text

    https://www.commcarehq.org/a/[domain]/fixtures

(The string in the Table ID column.)

**Sample Input:**

.. code-block:: text

    https://www.commcarehq.org/a/demo/api/v0.4/fixture/1J9NF7B4FTH73435PYJJSL5SJ/

**Sample Output:**

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
-------------------------

**Purpose:**
    Create or edit lookup tables by uploading an Excel file containing table data.

**URL:**

.. code-block:: text

    https://www.commcarehq.org/a/[domain]/fixtures/fixapi/

**Method:**
    POST

**Authorization:**
    Basic Authorization

**Input Parameters:**

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

**Sample cURL Request:**

.. code-block:: text

    curl -v https://www.commcarehq.org/a/myproject/fixtures/fixapi/ -u user@domain.com:password \
         -F "file-to-upload=@fixtures.xlsx" \
         -F "replace=true"

(You may also omit the ':' and password, and curl will request it. This will have the benefit of not showing your password on your screen or storing it in your history.)

**Response:** JSON output with the following parameters.

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
---------------------------

**Purpose:**
    Manage lookup tables via API calls.

**Authentication:**
    All URL endpoints should be utilized as part of a cURL authentication command. For more information, please review Authentication.

**Base URL:**

.. code-block:: text

    https://www.commcarehq.org/a/[domain]/api/[version]/lookup_table/

**Supported Methods:**

.. list-table::
   :header-rows: 1

   * - Method
     - Description
   * - GET
     - List lookup tables
   * - POST
     - Create a new lookup table

**Sample Output:**

.. code-block:: json

    {
        "meta": {
            "limit": 20,
            "next": null,
            "offset": 0,
            "previous": null,
            "total_count": 6
        },
        "objects": [
            {
                "fields": [
                    {"field_name": "name", "properties": ["lang"]},
                    {"field_name": "price", "properties": []}
                ],
                "id": "bcf49791f7f04f09bd46262097e107f2",
                "is_global": true,
                "resource_uri": "",
                "tag": "vaccines"
            }
        ]
    }

**Create Lookup Table:**

**URL:**

.. code-block:: text

    https://www.commcarehq.org/a/[domain]/api/[version]/lookup_table/

**Input Parameters:**

.. list-table::
   :header-rows: 1

   * - Name
     - Description
   * - tag*
     - Lookup table name
   * - fields*
     - Fields and their properties
   * - is_global
     - Boolean if the lookup table is accessible to all users (default: false)

**Sample Input:**

.. code-block:: json

    {
        "tag": "vaccines", 
        "fields": [
            {"field_name": "name", "properties": ["lang"]},
            {"field_name": "price", "properties": []}
        ],
        "is_global": true
    }

**Edit or Delete Lookup Table:**

**URL:**

.. code-block:: text

    https://www.commcarehq.org/a/[domain]/api/[version]/lookup_table/[lookup_table_id]

**Supported Methods:**

.. list-table::
   :header-rows: 1

   * - Method
     - Description
   * - GET
     - Get lookup table
   * - PUT
     - Edit lookup table
   * - DELETE
     - Delete lookup table

**Sample Input:**

.. code-block:: json

    {
        "tag": "vaccines", 
        "fields": [
            {"field_name": "name", "properties": ["lang"]},
            {"field_name": "price", "properties": []}
        ]
    }

Lookup Table Rows API
---------------------

**Purpose:**
    Manage lookup table rows via API calls.

**Base URL:**

.. code-block:: text

    https://www.commcarehq.org/a/[domain]/api/[version]/lookup_table_item/

**Supported Methods:**

.. list-table::
   :header-rows: 1

   * - Method
     - Description
   * - GET
     - List lookup table rows

**Sample Output:**

.. code-block:: json

    {
        "meta": {
            "limit": 20,
            "next": null,
            "offset": 0,
            "previous": null,
            "total_count": 15
        },
        "objects": [
            {
                "data_type_id": "bcf49791f7f04f09bd46262097e107f2",
                "fields": {
                    "name": {"field_list": [{"field_value": "MMR", "properties": {"lang": "en"}}]},
                    "price": {"field_list": [{"field_value": "7", "properties": {}}]}
                },
                "id": "e8433b25e60c4e228b0c7a679af2847b",
                "sort_key": 2
            }
        ]
    }

**Create Lookup Table Row:**

**URL:**

.. code-block:: text

    https://www.commcarehq.org/a/[domain]/api/[version]/lookup_table_item/

**Input Parameters:**

.. list-table::
   :header-rows: 1

   * - Name
     - Description
   * - data_type_id*
     - ID of a lookup table
   * - fields*
     - Fields and their properties

**Sample Input:**

.. code-block:: json

    {
        "data_type_id": "bcf49791f7f04f09bd46262097e107f2", 
        "fields": {
            "name": {"field_list": [{"field_value": "MMR", "properties": {"lang": "en"}}]},
            "price": {"field_list": [{"field_value": "7", "properties": {}}]}
        }
    }

**Edit or Delete Lookup Table Row:**

**URL:**

.. code-block:: text

    https://www.commcarehq.org/a/[domain]/api/[version]/lookup_table_item/[lookup_table_item_id]

**Supported Methods:**

.. list-table::
   :header-rows: 1

   * - Method
     - Description
   * - GET
     - Get lookup table row
   * - PUT
     - Edit lookup table row
   * - DELETE
     - Delete lookup table row

**Sample Input:**

.. code-block:: json

    {
        "data_type_id": "bcf49791f7f04f09bd46262097e107f2", 
        "fields": {
            "name": {"field_list": [{"field_value": "MMR", "properties": {"lang": "en"}}]},
            "price": {"field_list": [{"field_value": "10", "properties": {}}]}
        }
    }


