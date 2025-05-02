Location API v1
===============

**Note:** see :doc:`/api/locations-v2` for a newer version of this API that provides some additional functionality.

Data format
-----------

Individual locations are presented with the same serialization format in each endpoint

**Sample JSON Output**

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


List Locations
--------------

**Base URL**

.. code-block:: text

    GET https://www.commcarehq.org/a/[domain]/api/location/v1/

Locations can be filtered by the following attributes as request parameters:

**Input Parameters**

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

**Sample JSON Output**

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

    GET https://www.commcarehq.org/a/[domain]/api/location/v1/[location_id]

This will output the same information displayed above, but for a single location
