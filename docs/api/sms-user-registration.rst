SMS Mobile Worker Registration API
==================================

Overview
--------
**Purpose**
Initiate the SMS self-registration workflow for mobile workers. This performs the same functionality as the Messaging -> Mobile Worker Registration page, only over API.

**Project Prerequisites**
Your project must have a **PRO plan or higher** to use this feature, and you must enable **"SMS Mobile Worker Registration"** on the Messaging -> General Settings page.

Endpoint Specifications
-----------------------

**Base URL**

.. code-block:: text

    https://www.commcarehq.org/a/[domain]/api/[version]/sms_user_registration/

**Available since** ``v0.5``

**Method** ``POST``

**Authentication**
For more information, please review  `API Authentication <https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2279637003/CommCare+API+Overview#API-Authentication>`_.

Request & Response Details
---------------------------

**Input Parameters**

.. list-table:: 
   :widths: 20 10 10 60
   :header-rows: 1

   * - Name
     - Type
     - Required
     - Description
   * - app_id
     - string
     - Yes
     - The unique identifier used by CommCareHQ to identify the app that will be installed on the user's phone for Android users.
   * - users
     - list of json objects
     - Yes
     - A list of json objects representing the users to send the SMS registration invitation to.
   * - android_only
     - bool
     - No
     - Set to true to assume users are all Android users. The system will not ask users via SMS about their device type.
   * - require_email
     - bool
     - No
     - Set to true to make email address a required field on the self-registration page for Android users.
   * - custom_registration_message
     - string
     - No
     - A custom SMS message sent instead of the system's default message. Use `{}` as a placeholder for the registration URL.

**Users List JSON Structure**

.. list-table:: **Input Structure**
   :widths: 20 10 10 60
   :header-rows: 1

   * - Name
     - Type
     - Required
     - Description
   * - phone_number
     - string
     - Yes
     - The user's phone number, in E.164 format.
   * - custom_user_data
     - json object
     - No
     - Custom user data to be set when the user registers.


.. list-table:: **Output Structure**
   :widths: 20 10 70
   :header-rows: 1

   * - Name
     - Type
     - Description
   * - success_numbers
     - list of string
     - List of phone numbers that were successfully processed.
   * - invalid_format_numbers
     - list of string
     - List of phone numbers that could not be processed due to invalid format.
   * - numbers_in_use
     - list of string
     - List of phone numbers already registered.

**Sample Usage**

- *Simple Input*

.. code-block:: json

    {
      "app_id": "abcd1234abcd1234",
      "users": [
        {"phone_number": "+16175551234"}
      ]
    }

- *Complex Input*

.. code-block:: json

    {
      "app_id": "abcd1234abcd1234",
      "android_only": true,
      "require_email": true,
      "custom_registration_message": "Please register a new user here: {}",
      "users": [
        {
          "phone_number": "+16175551234",
          "custom_user_data": {
            "customdata1": "foo",
            "customdata2": "X"
          }
        },
        {
          "phone_number": "+16175555512",
          "custom_user_data": {
            "customdata1": "bar",
            "customdata2": "Y"
          }
        }
      ]
    }

**Sample Output**

.. code-block:: json

    {
      "success_numbers": ["+16175551234"],
      "invalid_format_numbers": [],
      "numbers_in_use": []
    }
