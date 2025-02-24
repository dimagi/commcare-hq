Web User Edit
=============

Overview
---------

**Purpose**
    Edit Web User.

**Permissions Required**
    - Edit Web Users
    - Edit Access API's

Endpoint Specifications
-----------------------
**Base URL**

.. code-block:: text

    https://www.commcarehq.org/a/[domain]/api/web-user/[version]/[id]/

**Method**

.. code-block:: text

    PATCH

**Authentication:**
    For more information, please review `API Authentication <https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2279637003/CommCare+API+Overview#API-Authentication>`_.

Request & Response Details
---------------------------

**Input Parameters**

- ``role``: Role of user (e.g., ``App Editor``)
- ``primary_location_id``: The location ID of the primary location; must be one of the assigned locations (e.g., ``26fc44e2792b4f2fa8ef86178f0a958e``)
- ``assigned_location_ids``: A list of ``location_ids`` that the web user will be assigned to.
- ``profile``: Profile to assign to the user (e.g., ``Facility User``)
- ``user_data``: Any additional custom data associated with the user.
- ``tableau_role``: Tableau Role of the user (Options: ``Explorer``, ``ExplorerCanPublish``, ``SiteAdministratorExplorer``, ``Viewer``, ``Unlicensed``)
- ``tableau_groups``: List of Tableau Groups the user is assigned to (e.g., ``["city", "county"]``)

**Sample Input (JSON Format)**

.. code-block:: json

    {
        "role":"App Editor",
        "primary_location_id":"26fc44e2792b4f2fa8ef86178f0a958e",
        "assigned_location_ids":["26fc44e2792b4f2fa8ef86178f0a958e", "c1b029932ed442a6a846a4ea10e46a78"],
        "profile": "Facility User",
        "user_data":{
            "Can Edit Client":"yes",
            "Can View Data": "yes",
            "Can Edit Data": ""
        },
        "tableau_role":"Viewer",
        "tableau_groups":["city", "county"]
    }

**Sample Output (JSON Format)**

.. code-block:: json

    {
        "assigned_location_ids": [
            "26fc44e2792b4f2fa8ef86178f0a958e",
            "c1b029932ed442a6a846a4ea10e46a78"
        ],
        "default_phone_number": null,
        "email": "test@gmail.com",
        "first_name": "Test",
        "id": "ce3ebe5e2a3f4b238cc36ebad68a1a70",
        "is_admin": false,
        "permissions": {
            "access_all_locations": true,
            "access_web_apps": true,
            "edit_user_profile": true,
            "report_an_issue": true,
            "view_user_tableau_config": true,
            "view_web_users": true
        },
        "phone_numbers": [],
        "primary_location_id": "26fc44e2792b4f2fa8ef86178f0a958e",
        "profile": "Blue",
        "resource_uri": "/a/jonathanlocal/api/web-user/v1/ce3ebe5e2a3f4b238cc36ebad68a1a70/",
        "role": "App Editor",
        "tableau_groups": ["city", "county"],
        "tableau_role": "Viewer",
        "user_data": {
            "commcare_profile": 9,
            "Can Edit Client":"yes",
            "Can View Data": "yes",
            "Can Edit Data": ""
        },
        "username": "test@gmail.com"
    }



User Identity API
=================

Overview
---------
**Purpose**
    Look up the authenticated web user's details.

Endpoint Specifications
-----------------------
**Base URL**

.. code-block:: text

    https://www.commcarehq.org/api/v0.5/identity/

Request & Response Details
---------------------------

**Sample Response:**

.. code-block:: json

    {
      "id": "672bdfc8-3629-10e0-9e24-005057aa7fe5",
      "username": "demo@dimagi.com",
      "first_name": "Demo",
      "last_name": "User",
      "email": "demo@dimagi.com"
    }
