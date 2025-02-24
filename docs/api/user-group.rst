Group API
=========

List Groups
-----------

Endpoint Specifications
~~~~~~~~~~~~~~~~~~~~~~~

**URL**

.. code-block:: text

    https://www.commcarehq.org/a/[domain]/api/[version]/group/

**API Authentication**
    All URL endpoints should be utilized as part of a cURL authentication command. For more information, please review `API Authentication <https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2279637003/CommCare+API+Overview#API-Authentication>`_.

Request & Response Details
~~~~~~~~~~~~~~~~~~~~~~~~~~

**Input Parameters**

.. list-table::
   :header-rows: 1

   * - Name
     - Description
     - Example
   * - format
     - Return data format (optional). Supported: json (default), xml
     - format=xml

**Sample Output**

.. code-block:: json

    {
      "meta": {
         "limit": 20, 
         "next": null, 
         "offset": 0, 
         "previous": null, 
         "total_count": 3
      }, 
      "objects": [
         {
             "case_sharing": false, 
             "domain": "cloudcaredemo", 
             "id": "1eb59d6938fc7e510254d8c2f63d944f", 
             "metadata": {}, 
             "name": "Wozzle", 
             "path": [], 
             "reporting": true, 
             "users": ["91da6b1c78699adfb8679b741caf9f00", "8a642f722c9e617eeed29290e409fcd5"]
         }
      ]
    }

Bulk API
--------

Endpoint Specifications
~~~~~~~~~~~~~~~~~~~~~~~

**URL**

.. code-block:: text

    https://www.commcarehq.org/a/[domain]/api/[version]/group/

**Supported Methods**

.. list-table::
   :header-rows: 1

   * - Method
     - Description
   * - POST
     - Create group
   * - PATCH
     - Create multiple groups

Request & Response Details
~~~~~~~~~~~~~~~~~~~~~~~~~~

**Input Parameters**

.. list-table::
   :header-rows: 1

   * - Name
     - Description
     - Example
   * - name*
     - Group name
     - Wozzle
   * - case_sharing
     - Whether users within this group will share cases with other members of this group
     - true/false (default=false)
   * - reporting
     - Whether this group's name will appear in the group filter list for reports
     - true/false (default=true)
   * - users
     - List of all user IDs belonging to the group. This is optional to specify.
     - ["91da6b1c78699adfb8679b741caf9f00", "8a642f722c9e617eeed29290e409fcd5"]
   * - metadata
     - Any additional custom data associated with the group. This is optional to specify.
     - {"localization": "Ghana"}

**Output Parameters**

.. list-table::
   :header-rows: 1

   * - Name
     - Description
     - Example
   * - id
     - Group UUID
     - 3c5a623af057e23a32ae4000cf291339

**Sample Input**

- *Single Group*

.. code-block:: json

    {
      "case_sharing": false,
      "metadata": {
        "localization": "Ghana"
      },
      "name": "Wozzle",
      "reporting": true,
      "users": [
        "91da6b1c78699adfb8679b741caf9f00",
        "8a642f722c9e617eeed29290e409fcd5"
      ]
    }

- *Multiple Groups (can include all other information from single group creation)*

.. code-block:: json

    {
      "objects": [
        {
          "case_sharing": false, 
          "name": "Test 1", 
          "reporting": true
        },
        {
          "case_sharing": true, 
          "name": "Test 2", 
          "reporting": true
        }
      ]
    }

Individual API
--------------

Endpoint Specifications
~~~~~~~~~~~~~~~~~~~~~~~

**URL**

.. code-block:: text

    https://www.commcarehq.org/a/[domain]/api/[version]/group/[group_id]

**Supported Methods**

.. list-table::
   :header-rows: 1

   * - Method
     - Description
   * - GET
     - Get group
   * - PUT
     - Edit group
   * - DELETE
     - Delete group

Request & Response Details
~~~~~~~~~~~~~~~~~~~~~~~~~~

**Input Parameters**

.. list-table::
   :header-rows: 1

   * - Name
     - Description
     - Example
   * - name
     - Group name
     - Wozzle
   * - case_sharing
     - Whether users within this group will share cases with other members of this group
     - true/false
   * - reporting
     - Whether this group's name will appear in the group filter list for reports
     - true/false
   * - users
     - List of all user IDs belonging to the group . his will replace any existing users for the group.
     - ["91da6b1c78699adfb8679b741caf9f00", "8a642f722c9e617eeed29290e409fcd5"]
   * - metadata
     - Any additional custom data associated with the group. This will replace any existing custom data for the group.
     - {"localization": "Ghana"}

**Sample Input**

.. code-block:: json

    {
      "case_sharing": false,
      "metadata": {
        "localization": "Ghana"
      },
      "name": "Wozzle",
      "reporting": true,
      "users": [
        "91da6b1c78699adfb8679b741caf9f00",
        "8a642f722c9e617eeed29290e409fcd5"
      ]
    }
