Location API v2
================

V2 of the Location API updates the serialization used in v1 and adds the
ability to create and update locations, one at a time or in bulk. The API
can also be ordered by ``last_modified`` from oldest to newest with the
parameter ``order_by=last_modified``, or from newest to oldest with
``order_by=-last_modified``. This can be used in conjunction with the
``last_modified.gte`` parameter to only fetch locations modified since your
last data pull.

.. openapi:: spec/location-v2.json

Create Location (Individual)
-----------------------------

**Required Fields**

- ``name``
- ``location_type_code``

**Notes on Optional Fields**

.. list-table::
   :header-rows: 1

   * - Field
     - Note
   * - ``site_code``
     - The system will generate one if not provided. Must be unique on the domain.
   * - ``parent_location_id``
     - The ID will be validated to ensure the parent exists, supports child locations, and has no duplicate names.

Update Location (Individual)
-----------------------------

**Notes on Editable Fields**

.. list-table::
   :header-rows: 1

   * - Field
     - Note
   * - ``name``
     - Must be unique among siblings.
   * - ``site_code``
     - Must be unique on the domain.
   * - ``location_type_code``
     - If the location has a parent, the new location type must be a valid child type of that parent.
   * - ``parent_location_id``
     - The parent must exist, be able to have child locations of this type, and must not already have a child with the same name.

If any part of the location's update fails due to invalid fields, the update
will not occur at all.

Create and Update Locations (in Bulk)
--------------------------------------

Even though the bulk method is ``PATCH``, you can also create locations, as
well as update them, using this method.

The request body should be a list of locations, with each location as a JSON
dictionary, wrapped in an ``objects`` list -- this differs from the object
schema shown above, which describes a single location. Include
``location_id`` in a location's dictionary if you want to update it, and
omit it if you want to create it.

When creating a location via this method, the API uses the same validation
as the create endpoint. For updating, it uses the same validation as the
update endpoint.

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

With this request body, the first dictionary will create a location called
"Newtown", and update the location with ID
``eea759ae08044807be749f665a1fd39a`` to have the name "Springfield".

The bulk ``PATCH`` request is atomic: if validation fails for a single
location in the request, none of the locations will be created or updated.
