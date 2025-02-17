List Locations
-------------

**Base URL:**

.. code-block:: text

    GET https://www.commcarehq.org/a/[domain]/api/[version]/location/

**Input Parameters:**

v0.5 Locations can be filtered by the following attributes as request parameters:

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

**Sample JSON Output (v0.5):**

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
          "location_type": "https://www.commcarehq.org/a/[domain]/api/v0.5/location_type/1/",
          "longitude": null,
          "name": "Namibia",
          "parent": null,
          "resource_uri": "https://www.commcarehq.org/a/[domain]/api/v0.5/location/f373a6837c1243938abfc56618cce88b/",
          "site_code": "namibia"
        }
      ]
    }

**v0.6**

The main distinctions between the v0.5 and v0.6 GET endpoints are that v0.6:

- Removes a few fields and adds a few fields from the response (there is no ``external_id`` with v0.6, for example, but there is ``parent_location_id``).
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

Also notice how compared to v0.5, the v0.6 location data has just the ``location_id``, no resource URL.
