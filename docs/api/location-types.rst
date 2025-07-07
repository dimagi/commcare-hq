Location Types API
==================

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
