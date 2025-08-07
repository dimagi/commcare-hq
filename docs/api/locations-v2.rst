Location API v2
===============

V2 of the Location API updates the serilization used in v1 and adds the ability
to create and update locations, one at a time or in bulk.

Data format
-----------

Individual locations are presented with the same serialization format in each endpoint

**Sample JSON Output**

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


List Locations
--------------

**Base URL**

.. code-block:: text

    GET https://www.commcarehq.org/a/[domain]/api/location/v2/

Locations can be filtered by the following attributes as request parameters:

**Input Parameters (v2)**

.. list-table::
   :header-rows: 1

   * - Name
     - Description
     - Example
   * - ``format``
     - Data format returned, defaults to xml
     - ```?format=json``
   * - ``site_code``
     - Site code for the location
     - ``?site_code=boston``
   * - ``name``
     - The location's name (case sensitive)
     - ``?name=Boston``
   * - ``location_type_code``
     - The location's type code
     - ``?location_type_code=city``
   * - ``parent_location_id``
     - The UUID of the location's direct parent
     - ``?parent_location_id=5ce87caa-a739-4a61-a0cb-559f84a9b4b7``
   * - ``last_modified.gte``
     - Locations last modified on or after a specific date or datetime
     - ``?last_modified.gte=2024-01-01``
   * - ``last_modified.gt``
     - Locations last modified after a specific date or datetime
     - ``?last_modified.gt=2024-01-01``
   * - ``last_modified.lt``
     - Locations last modified before a specific date or datetime
     - ``?last_modified.lt=2024-01-01``
   * - ``last_modified.lte``
     - Locations last modified on or before a specific date or datetime
     - ``?last_modified.lte=2024-01-01``

The API can also be ordered by ``last_modified`` from oldest to newest with the
parameter ``order_by=last_modified``, or from newest to oldest with
``order_by=-last_modified``. This can be used in conjunction with the
``last_modified.gte`` parameter to only fetch locations modified since your last
data pull.

**Sample JSON output**

.. code-block:: json

    {
      "meta": {
        "limit": 20,
        "next": null,
        "offset": 0,
        "previous": null,
        "total_count": 2
      },
      "objects": ["<array of location objects>"]
    }

Location Details
----------------

**Base URL**

.. code-block:: text

    GET https://www.commcarehq.org/a/[domain]/api/location/v2/[location_id]


Create Location (Individual)
----------------------------

**Description**

Create an individual location.

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

Allows editing an individual location.

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

You may also create and update locations in bulk. Even though the method is
PATCH, you can also create locations as well as update using this method.

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
