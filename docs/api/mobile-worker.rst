
User Creation (Mobile Worker)
=============================

Overview
--------

**Purpose**
    Create a CommCare (mobile-worker) user.

**Permissions Required**
    - Edit Mobile Workers
    - Edit Access API's

Endpoint Specifications
-----------------------

**URL**

.. code-block:: text

    https://www.commcarehq.org/a/[domain]/api/[version]/user/

**Method**

.. code-block:: text

    POST

Request & Response Details
---------------------------

**Input Parameters** (* indicates required)

- ``username*``: User name of user (e.g., ``jdoe``)
- ``password*``: User password (e.g., ``qwer1234``)
- ``first_name``: First name of user (e.g., ``John``)
- ``last_name``: Last name of user (e.g., ``Doe``)
- ``email``: Email address of user (e.g., ``john.doe@example.org``)
- ``phone_numbers``: List of all phone numbers of the user. The first one will be set as the default number.
- ``groups``: List of all group IDs belonging to the user.
- ``user_data``: Any additional custom data associated with the user.
- ``language``: User language (e.g., ``en``)
- ``primary_location``: The location ID of the primary location; must be one of the assigned locations (e.g., ``26fc44e2792b4f2fa8ef86178f0a958e``)
- ``locations``: A list of ``location_ids`` that the mobile worker will be assigned to.

**Output Parameters**

- ``user_id``: User UUID (e.g., ``3c5a623af057e23a32ae4000cf291339``)

**Sample Input (JSON Format)**

.. code-block:: json

    {
       "username": "jdoe",
       "password": "qwer1234",
       "first_name": "John",
       "last_name": "Doe",
       "default_phone_number": "+50253311399",
       "email": "jdoe@example.org",
       "language": "en",
       "phone_numbers": [
          "+50253311399",
          "50253314588"
       ],
       "groups": [
          "9a0accdba29e01a61ea099394737c4fb",
          "b4ccdba29e01a61ea099394737c4fbf7" 
       ],
       "primary_location": "26fc44e2792b4f2fa8ef86178f0a958e", 
       "locations": ["26fc44e2792b4f2fa8ef86178f0a958e", "c1b029932ed442a6a846a4ea10e46a78"],
       "user_data": {
          "chw_id": "13/43/DFA"
       }
    }



User Edit (Mobile Worker)
=========================

Overview
--------

**Purpose**
    Edit CommCare (mobile-worker) user.

**Permissions Required**
    Edit Mobile Workers & Edit Access APIs

**Authentication**
    For more information, please review the `API Authentication <https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2279637003/CommCare+API+Overview#API-Authentication>`_.

Endpoint Specifications
-----------------------

**URL**

.. code-block:: text

    https://www.commcarehq.org/a/[domain]/api/[version]/user/[id]/

**Method**
    PUT

**Request Header**
    You must specify in the request header that the **Content-Type** is **application/json**.


Request & Response Details
---------------------------

**Input Parameters**

.. list-table::
   :header-rows: 1

   * - Name
     - Description
     - Example
   * - first_name
     - First name of user
     - John
   * - last_name
     - Last name of user
     - Doe
   * - email
     - Email address of user
     - john.doe@example.org
   * - phone_numbers
     - List of all phone numbers of the user (replaces existing ones)
     - ["+50253311399", "50253314588"]
   * - groups
     - List of all group IDs belonging to the user (replaces existing groups)
     - ["9a0accdba29e01a61ea099394737c4fb", "b4ccdba29e01a61ea099394737c4fbf7"]
   * - user_data
     - Any additional custom data associated with the user (replaces existing custom data).
       Note that user data may include system data affecting various features,
       so it is advised to pull the user's current data and edit it, rather than
       completely overwriting user data. To get the user's current data, use the
       single user URL provided at List Mobile Workers API.
     - {"chw_id": "13/43/DFA"}
   * - language
     - User language
     - en
   * - password
     - New password for user
     - fake-password-123
   * - primary_location
     - The location ID of the primary location (must be one of the user's locations)
     - 26fc44e2792b4f2fa8ef86178f0a958e
   * - locations
     - List of location IDs assigned to the user (replaces existing locations)
     - ["26fc44e2792b4f2fa8ef86178f0a958e", "c1b029932ed442a6a846a4ea10e46a78"]

**Sample Input**

.. code-block:: json

    {
       "first_name": "John",
       "last_name": "Doe",
       "email": "jdoe@example.org",
       "language": "en",
       "password": "new password",
       "phone_numbers": [
          "+50253311399",
          "50253314588"
       ],
       "groups": [
          "9a0accdba29e01a61ea099394737c4fb",
          "b4ccdba29e01a61ea099394737c4fbf7"
       ],
       "primary_location": "26fc44e2792b4f2fa8ef86178f0a958e", 
       "locations": ["26fc44e2792b4f2fa8ef86178f0a958e", "c1b029932ed442a6a846a4ea10e46a78"],
       "user_data": {
          "chw_id": "13/43/DFA"
       }
    }

User Delete (Mobile Worker)
===========================

Overview
--------

**Purpose**
    Delete a CommCare (mobile-worker) user.

**Permissions Required**
    - Edit Mobile Workers
    - Edit Access API's

Endpoint Specifications
-----------------------

**URL**

.. code-block:: text

    https://www.commcarehq.org/a/[domain]/api/[version]/user/[id]/

**Method**

.. code-block:: text

    DELETE

**Authentication**
    For more information, please review  `API Authentication <https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2279637003/CommCare+API+Overview#API-Authentication>`_.
