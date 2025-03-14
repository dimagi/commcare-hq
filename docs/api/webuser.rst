Web User Invitation Creation
============================
Overview
--------

**Purpose**
    Create Invitation for a Web User.

**Permissions Required**
    Edit Web Users & Edit Access API's

Endpoint Specifications
-----------------------

**Base URL**

.. code-block:: text

        https://www.commcarehq.org/a/[domain]/api/invitation/[version]/

**Method**

.. code-block:: text

    POST

**Authentication**
    For more information, please review `API Authentication <https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2279637003/CommCare+API+Overview#API-Authentication>`_.

Request & Response Details
---------------------------

**Input Parameters**

(* means required)

.. list-table::
   :header-rows: 1

   * - Name
     - Description
     - Example
   * - email*
     - Email address of user
     - jdoe@dimagi.com
   * - role*
     - Role of user
     - App Editor
   * - primary_location_id
     - The location id of the primary location, it must be one of the assigned locations
     - 26fc44e2792b4f2fa8ef86178f0a958e
   * - assigned_location_ids
     - A list of location_ids that the web user will be assigned to. Location id can be acquired by `Location API <locations.rst>`_.
     - ["26fc44e2792b4f2fa8ef86178f0a958e", "c1b029932ed442a6a846a4ea10e46a78"]
   * - profile
     - Profile to assign to the user
     - Facility User
   * - user_data
     - Any additional custom data associated with the user (see examples)
     - (see examples)
   * - tableau_role
     - Tableau Role of the user. Options are: “Explorer”, “ExplorerCanPublish”, “SiteAdministratorExplorer”, “Viewer”, and “Unlicensed”
     - Viewer
   * - tableau_groups
     - List of Tableau Groups the user is assigned to
     - ["city", "county"]

**Output Parameters**

.. list-table::
   :header-rows: 1

   * - Name
     - Description
     - Example
   * - id
     - Invitation UUID
     - 844b88b3-8f4a-43f8-ba39-62e3014a6998

**Sample input (JSON)**

.. code-block:: json

    {
        "email": "jdoe@dimagi.com",
        "role": "App Editor",
        "primary_location_id": "26fc44e2792b4f2fa8ef86178f0a958e",
        "assigned_location_ids": [
            "26fc44e2792b4f2fa8ef86178f0a958e",
            "c1b029932ed442a6a846a4ea10e46a78"
        ],
        "profile": "Facility User",
        "user_data": {
            "Can Edit Client": "yes",
            "Can View Data": "yes"
        },
        "tableau_role": "Viewer",
        "tableau_groups": ["city", "county"]
    }

**Sample output (JSON)**

.. code-block:: json

    {
        "email": "jdoe@dimagi.com",
        "role": "App Editor",
        "primary_location_id": "26fc44e2792b4f2fa8ef86178f0a958e",
        "assigned_location_ids": [
            "26fc44e2792b4f2fa8ef86178f0a958e",
            "c1b029932ed442a6a846a4ea10e46a78"
        ],
        "profile": "Facility User",
        "user_data": {
            "Can Edit Client": "yes",
            "Can View Data": "yes"
        },
        "tableau_role": "Viewer",
        "tableau_groups": ["city", "county"]
    }


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

.. list-table::
   :header-rows: 1

   * - Name
     - Description
     - Example
   * - role
     - Role of user
     - App Editor
   * - primary_location_id
     - The location id of the primary location, it must be one of the assigned locations
     - 26fc44e2792b4f2fa8ef86178f0a958e
   * - assigned_location_ids
     - A list of location_ids that the web user will be assigned to. Location id can be acquired by `Location API <locations.rst>`_.
     - ["26fc44e2792b4f2fa8ef86178f0a958e", "c1b029932ed442a6a846a4ea10e46a78"]
   * - profile
     - Profile to assign to the user
     - Facility User
   * - user_data
     - Any additional custom data associated with the user
     - (see examples)
   * - tableau_role
     - Tableau Role of the user. Options are: “Explorer”, “ExplorerCanPublish”, “SiteAdministratorExplorer”, “Viewer”, and “Unlicensed”
     - Viewer
   * - tableau_groups
     - List of Tableau Groups the user is assigned to
     - ["city", "county"]


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
      "eulas": "[LicenseAgreement(date=datetime.datetime(2024, 5, 14, 18, 39, 51, 495449), doc_type='LicenseAgreement', signed=True, type='End User License Agreement', user_id=None, user_ip=None, version='3.0')]",
      "first_name": "Test",
      "id": "ce3ebe5e2a3f4b238cc36ebad68a1a70",
      "is_admin": false,
      "last_name": "",
      "permissions": {
        "access_all_locations": true,
        "access_api": false,
        "access_default_login_as_user": false,
        "access_mobile_endpoints": false,
        "access_release_management": false,
        "access_web_apps": true,
        "commcare_analytics_roles": false,
        "commcare_analytics_roles_list": [],
        "doc_type": "HqPermissions",
        "download_reports": false,
        "edit_apps": false,
        "edit_billing": false,
        "edit_commcare_analytics": false,
        "edit_commcare_users": false,
        "edit_data": false,
        "edit_data_dict": false,
        "edit_file_dropzone": false,
        "edit_groups": false,
        "edit_linked_configurations": false,
        "edit_locations": false,
        "edit_messaging": false,
        "edit_motech": false,
        "edit_reports": false,
        "edit_shared_exports": false,
        "edit_ucrs": false,
        "edit_user_profile": true,
        "edit_user_profile_list": [],
        "edit_user_tableau_config": false,
        "edit_users_in_groups": false,
        "edit_users_in_locations": false,
        "edit_web_users": false,
        "limited_login_as": false,
        "login_as_all_users": false,
        "manage_attendance_tracking": false,
        "manage_data_registry": false,
        "manage_data_registry_list": [],
        "manage_domain_alerts": false,
        "report_an_issue": true,
        "view_apps": false,
        "view_commcare_analytics": false,
        "view_commcare_users": false,
        "view_data_dict": false,
        "view_data_registry_contents": false,
        "view_data_registry_contents_list": [],
        "view_file_dropzone": true,
        "view_groups": false,
        "view_locations": false,
        "view_report_list": [],
        "view_reports": false,
        "view_roles": false,
        "view_tableau": false,
        "view_tableau_list": [],
        "view_user_tableau_config": true,
        "view_web_users": true,
        "web_apps_list": []
      },
      "phone_numbers": [],
      "primary_location_id": "26fc44e2792b4f2fa8ef86178f0a958e",
      "profile": "Blue",
      "resource_uri": "/a/jonathanlocal/api/web-user/v1/ce3ebe5e2a3f4b238cc36ebad68a1a70/",
      "role": "App Editor",
      "tableau_groups": [
        "city, county"
      ],
      "tableau_role": "Viewer",
      "user_data": {
        "commcare_profile": 9,
        "Can Edit Client": "yes",
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
