Location APIs
=============

Version v1 is read-only. It allows you to list locations and get location details.

Version v2 has the same read-only list and details endpoints as v1 with just a few updates and adds the ability to create and update locations, one at a time or in bulk.

List Locations
--------------

**Base URL**

.. code-block:: text

    GET https://www.commcarehq.org/a/[domain]/api/location/v1/

**Input Parameters (v1)**

Locations can be filtered by the following attributes as request parameters:

.. list-table::
   :header-rows: 1

   * - Name
     - Description
   * - ``site_code``
     - Site code for the location
   * - ``external_id``
     - External identifier for the location
   * - ``created_at``
     - Timestamp when the location was created
   * - ``last_modified``
     - Timestamp of the last modification
   * - ``latitude``
     - Latitude coordinate of the location
   * - ``longitude``
     - Longitude coordinate of the location

**Sample JSON Output (v1)**

.. code-block:: json

    {
      "meta": {
        "limit": 20,
        "next": null,
        "offset": 0,
        "previous": null,
        "total_count": 2
      },
      "objects": [
        {
          "created_at": "2023-05-09T16:10:47.225938",
          "domain": "[domain]",
          "external_id": null,
          "id": 1,
          "last_modified": "2023-05-09T16:10:47.225947",
          "latitude": null,
          "location_data": {},
          "location_id": "f373a6837c1243938abfc56618cce88b",
          "location_type": "https://www.commcarehq.org/a/[domain]/api/location_type/v1/1/",
          "longitude": null,
          "name": "Namibia",
          "parent": null,
          "resource_uri": "https://www.commcarehq.org/a/[domain]/api/location/v1/f373a6837c1243938abfc56618cce88b/",
          "site_code": "namibia"
        }
      ]
    }

**v2**

The main distinctions between the v1 and v2 GET endpoints are that v2:

- Removes a few fields and adds a few fields from the response (there is no ``external_id`` with v2, for example, but there is ``parent_location_id``).
- Currently does not allow filtering on the list endpoint.

For the list endpoint, the "meta" section will look the same and the locations will still be in a list called "objects". But an individual location object will look like:

.. code-block:: json

    {
        "domain": "dimagi-test",
        "last_modified": "2024-03-11T19:29:16.845849",
        "latitude": "31.4100000000",
        "location_data": {
            "pop": "1001"
        },
        "location_id": "68e65fbc2dc840ff8bf03849e57aca88",
        "location_type_code": "county",
        "location_type_name": "County",
        "longitude": null,
        "name": "Fairfax County",
        "parent_location_id": "41b0bdfbae20428e9435ae8c3dcd22e7",
        "site_code": "fairfax_county"
    }

Also notice how compared to v1, the v2 location data has just the ``location_id``, no resource URL.

Location Details
----------------

**Base URL**

.. code-block:: text

    GET https://www.commcarehq.org/a/[domain]/api/location/v1/[location_id]

**Sample JSON Output (v1)**

.. code-block:: json

    {
      "created_at": "2023-05-09T16:10:47.225938",
      "domain": "[domain]",
      "external_id": null,
      "id": 1,
      "last_modified": "2023-05-09T16:10:47.225947",
      "latitude": null,
      "location_data": {},
      "location_id": "f373a6837c1243938abfc56618cce88b",
      "location_type": "https://www.commcarehq.org/a/[domain]/api/location_type/v1/1/",
      "longitude": null,
      "name": "Namibia",
      "parent": null,
      "resource_uri": "https://www.commcarehq.org/a/[domain]/api/location/v1/f373a6837c1243938abfc56618cce88b/",
      "site_code": "namibia"
    }

**v2**

You can get the details for an individual location using v2 as well. See the v2 section of the list documentation above for information on what single location object serialization looks like in v2.

Create Location (Individual)
----------------------------

**Description**

Create an individual location. Available from version v2.

**Base URL**

.. code-block:: text

    POST https://www.commcarehq.org/a/[domain]/api/location/v2/

**Required Fields**

- ``name``
- ``location_type_code``

**Other Fields (Optional)**

.. list-table::
   :header-rows: 1

   * - Field
     - Description
   * - ``site_code``
     - The system will generate one if not provided. Must be unique on the domain.
   * - ``latitude``
     - Latitude coordinate of the location.
   * - ``longitude``
     - Longitude coordinate of the location.
   * - ``location_data``
     - JSON dictionary instead of a string.
   * - ``parent_location_id``
     - The ID will be validated to ensure the parent exists, supports child locations, and has no duplicate names.

**Example Request Body**

.. code-block:: json

    {
        "latitude": "31.41",
        "location_data": {
            "pop": "1000"
        },
        "location_type_code": "city",
        "longitude": null,
        "name": "Greenville",
        "parent_location_id": "46329a9e1bad47158739d56f6f667165"
    }

Update Location (Individual)
----------------------------

**Description**

Allows editing an individual location. Available from version v2.

**Base URL**

.. code-block:: text

    PUT https://www.commcarehq.org/a/[domain]/api/location/v2/[location_id]

**Editable Fields**

.. list-table::
   :header-rows: 1

   * - Field
     - Description
   * - ``name``
     - Must be unique among siblings.
   * - ``site_code``
     - Must be unique on the domain.
   * - ``latitude``
     - Latitude coordinate of the location.
   * - ``longitude``
     - Longitude coordinate of the location.
   * - ``location_data``
     - Dictionary format.
   * - ``location_type_code``
     - If the location has a parent, the new location type must be a valid child type of that parent.
   * - ``parent_location_id``
     - The parent must exist, be able to have child locations of this type, and must not already have a child with the same name.

If a part of the location’s update fails due to invalid fields, the update will not occur at all.
If you wanted to update the location type and parent for the location, an example request body would be -

**Example Request Body**

.. code-block:: json

    {
        "location_type_code": "county",
        "parent_location_id": "46329a9e1bad47158739d56f6f667165"
    }


Create and Update Locations (in Bulk)
-------------------------------------

**Description**

Version v2 allows you to create and update locations in bulk. Even though the method is PATCH, you can also create locations as well as update using this method.

**Base URL**

.. code-block:: text

    PATCH https://www.commcarehq.org/a/[domain]/api/location/v2/

The request body should be a list of locations, with each location as a JSON dictionary (if you are using JSON). The list should be called ``objects``. Include ``location_id`` in the dictionary if you want to update a location, and don’t include it if you want to create a location.

When creating a location via this method, the API uses the same validation as the create endpoint. For updating, it uses the same validation as the update endpoint. For updating a location, see the table of allowed fields in the documentation for "Update". For creating, see the table of fields under "Create Location".

**Example Request Body**

.. code-block:: json

    {
        "objects": [
            {
                "name": "Newtown",
                "latitude": "31.41",
                "location_data": {
                    "pop": "1001"
                },
                "location_type_code": "city",
                "longitude": null,
                "parent_location_id": "46329a9e1bad47158739d56f6f667165"
            },
            {
                "location_id": "eea759ae08044807be749f665a1fd39a",
                "name": "Springfield",
                "latitude": "32.42",
                "location_data": {
                    "pop": "1004"
                }
            }
        ]
    }

With this request body, the first dictionary will create a location called "Newtown", and update a location with the ID ``eea759ae08044807be749f665a1fd39a`` to have the name "Springfield".

Lastly, the PATCH request is atomic. Meaning if validation fails for a single location in the request, none of the locations will be created or updated.

List Location Types
-------------------

**Description**

Retrieves a list of location types available in the specified domain.

**Base URL**

.. code-block:: text

    GET https://www.commcarehq.org/a/[domain]/api/location_type/v1/


**Sample JSON Output**

.. code-block:: json

    {
      "meta": {
        "limit": 20,
        "next": null,
        "offset": 0,
        "previous": null,
        "total_count": 1
      },
      "objects": [
        {
          "administrative": true,
          "code": "country",
          "domain": "[domain]",
          "id": 1,
          "name": "Country",
          "parent": null,
          "resource_uri": "https://www.commcarehq.org/a/[domain]/api/location_type/v1/1/",
          "shares_cases": false,
          "view_descendants": false
        }
      ]
    }

Location Type Details
---------------------

**Description**

Retrieves details for a specific location type.

**Base URL**

.. code-block:: text

    GET https://www.commcarehq.org/a/[domain]/api/location_type/v1/[id]


**Sample JSON Output**

.. code-block:: json

    {
      "administrative": true,
      "code": "country",
      "domain": "[domain]",
      "id": 1,
      "name": "Country",
      "parent": null,
      "resource_uri": "https://www.commcarehq.org/a/[domain]/api/location_type/v1/1/",
      "shares_cases": false,
      "view_descendants": false
    }
