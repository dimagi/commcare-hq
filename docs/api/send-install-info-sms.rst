Send CommCare Install Info over SMS
-----------------------------------

**Availability:**
    This feature is only available on CommCare version 2.44.4 and below. It is not supported in the current CommCare version available in the Play Store.

Overview
~~~~~~~~

**Purpose:**
    Use this API to facilitate the reinstallation of CommCare on the phones of already-registered users. All recipients should be on an Android phone. The users will receive two SMS messages: one with a link to the Google Play store to download and install CommCare, and another with the CommCare app install information used internally by CommCare.

**Project Prerequisites:**
    - Your project must have a PRO plan or higher to use this feature.
    - "SMS Mobile Worker Registration" must be enabled on the *Messaging -> General Settings* page.

**Authentication:**
    For more information, please review Authentication.

**Base URL:**

.. code-block:: text

    https://www.commcarehq.org/a/[domain]/api/[version]/sms_user_registration_reinstall/

**Available since:** v0_5

**Method:**

.. code-block:: text

    POST

**Input and Output Structure**
------------------------------

**Input Parameters:**

.. list-table::
    :header-rows: 1
    :widths: 20 10 10 50 20

    * - Name
      - Type
      - Required
      - Description
      - Example
    * - app_id
      - string
      - Yes
      - The unique identifier used by CommCareHQ to identify the app that will be installed on the user's phone.
      - "abcd1234abcd1234"
    * - users
      - list
      - Yes
      - A list of JSON objects representing the users to send the SMS information to.
      - [{"phone_number": "16175551234"}]
    * - reinstall_message
      - string
      - No
      - A custom SMS message to replace the default message. Ensure to leave a placeholder `{}` for the Play Store link.
      - "Click here to install CommCare: {}"

Each JSON object in the `users` list should have the following structure:

.. list-table::
    :header-rows: 1
    :widths: 20 10 10 50 20

    * - Name
      - Type
      - Required
      - Description
      - Example
    * - phone_number
      - string
      - Yes
      - The user's phone number, in E.164 format.
      - 16175551234

**Output Structure:**

.. list-table::
    :header-rows: 1
    :widths: 30 20 50 20

    * - Name
      - Type
      - Description
      - Example
    * - success_numbers
      - list[string]
      - List of successfully processed phone numbers.
      - ["16175551234"]
    * - invalid_format_numbers
      - list[string]
      - List of phone numbers with invalid formats.
      - ["1617JKL1234"]
    * - error_numbers
      - list[string]
      - List of phone numbers that encountered errors.
      - ["16175551234"]


**Sample Input (JSON Format):**

.. code-block:: json

    {
      "app_id": "abcd1234abcd1234",
      "users": [
        {"phone_number": "16175551234"}
      ]
    }

**Sample Output (JSON Format):**

.. code-block:: json

    {
      "success_numbers": ["16175551234"],
      "invalid_format_numbers": [],
      "error_numbers": []
    }
