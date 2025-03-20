List Web Users
==============

Overview
--------

**Purpose**
    Retrieve a list of web users or a single user.

**Base URL**

.. code-block:: 

    https://www.commcarehq.org/a/[domain]/api/[version]/web-user/

**Single User Request**

.. code-block:: 

    https://www.commcarehq.org/a/[domain]/api/[version]/web-user/[user_id]

**Authentication**
    All URL endpoints should be utilized as part of a cURL authentication command. For more information, please review `API Authentication <https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2279637003/CommCare+API+Overview#API-Authentication>`_.

**Permissions Required**
    Edit Web Users

Request & Response Details
---------------------------

**Input Parameters**

.. list-table::
   :header-rows: 1

   * - Name
     - Description
     - Example
   * - ``username``
     - Filter list by username
     - ``username=bob@example.com``

**Output Parameters**

.. list-table::
   :header-rows: 1

   * - Name
     - Description
     - Example
   * - ``id``
     - User UUID
     - ``3c5a623af057e23a32ae4000cf291339``
   * - ``username``
     - User name of user, including domain
     - ``jdoe@example.com``
   * - ``first_name``
     - First name of user
     - ``John``
   * - ``last_name``
     - Last name of user
     - ``Doe``
   * - ``default_phone_number``
     - Primary phone number of user
     - ``+50253311399``
   * - ``email``
     - Email address of user
     - ``john.doe@example.org``
   * - ``phone_numbers``
     - List of all phone numbers of the user
     - ``(see examples)``
   * - ``role``
     - Name of user role
     - ``(see examples)``
   * - ``permissions``
     - Object representing user's permissions
     - ``(see examples)``
   * - ``is_admin``
     - Whether the user is a project admin
     - ``(see examples)``

**Sample Usage**

.. code-block:: text

    https://www.commcarehq.org/a/demo/api/web-user/v1/

**Sample Output (JSON)**

.. code-block:: json

    {
       "meta":{
          "limit":20,
          "next":null,
          "offset":0,
          "previous":null,
          "total_count":2
       },
       "objects":[
          {
             "default_phone_number":null,
             "email":"admin@example.com",
             "first_name":"Joe",
             "id":"8f9756be9b1c7f28057d707b405d18f6",
             "is_admin": true,
             "last_name":"Admin",
             "permissions":{
                "doc_type":"Permissions",
                "edit_apps":true,
                "edit_commcare_users":true,
                "edit_data":true,
                "edit_web_users":true,
                "view_report_list":[],
                "view_reports":true
             },
             "phone_numbers":[],
             "resource_uri":"",
             "role":"Admin",
             "username":"admin@example.com"
          },
          {
             "default_phone_number":null,
             "email":"reporter@dimagi.com",
             "first_name":"Bob",
             "id":"73a1ce78809f7d077b4b3a01163e9186",
             "is_admin": false,
             "last_name":"Reporter",
             "permissions":{
                "doc_type":"Permissions",
                "edit_apps":false,
                "edit_commcare_users":false,
                "edit_data":false,
                "edit_web_users":false,
                "view_report_list":[],
                "view_reports":true
             },
             "phone_numbers":[],
             "resource_uri":"",
             "role":"Read Only",
             "username":"reporter@example.com"
          }
       ]
    }
