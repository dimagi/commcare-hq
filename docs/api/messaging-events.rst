Messaging Events
----------------

**Purpose:**
    To provide users access to the messaging data.

The data in this API is based on a nested data model:

- **Messaging Event**: The core data model representing a messaging event linked to a specific recipient and from a specific source (e.g., Conditional Alert).
- **Message**: The actual message that went to the user.
- A single event may have multiple messages (e.g., SMS surveys which will have one message per interaction with the recipient).

**Authentication**

For more information, please review `API Authentication <https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2279637003/CommCare+API+Overview#API-Authentication>`_.

**Base URL**

.. code-block:: text

    https://www.commcarehq.org/a/[domain]/api/[version]/messaging-event/

**Supported versions:** ``v0.5``

Filters
~~~~~~~

These are the filter parameters that the API call can use. Examples of how to use the filters in an API call appear below.

.. list-table:: Filter Parameters
   :widths: 15 30 20 30
   :header-rows: 1

   * - Name
     - Description
     - Filters On
     - Example
   * - limit
     - Number of records to return (Defaults to 20, maximum 5000)
     - -
     - ``limit=100``
   * - cursor
     - Used for pagination (value provided in API response)
     - -
     - -
   * - date.lt (less than)
     - Filter events before a specific date
     - event.date
     - ``date.lt=2021-05-01``
   * - date.lte (less than or equal to)
     - Filter events on or before a specific date
     - event.date
     - ``date.lte=2021-05-01``
   * - date.gt (greater than)
     - Filter events after a specific date
     - event.date
     - ``date.gt=2021-05-01``
   * - date.gte (greater than or equal to)
     - Filter events on or after a specific date
     - event.date
     - ``date.gte=2021-05-01``
   * - content_type
     - Filter on the content type of the event
     - event.content_type
     - ``content_type=sms``
   * - source
     - Filter on the source of the event
     - event.source
     - ``source=broadcast``
   * - status
     - Filter on the status of the event
     - event.status
     - ``status=error``
   * - phone_number
     - Filter on the recipient phone number
     - event.message.phone_number
     - -

Sorting
~~~~~~~
These sorting parameters can be applied to the existing search results alongside the filters.

.. list-table:: Sorting Parameters
   :widths: 30 70
   :header-rows: 1

   * - Sort Parameter
     - Description
   * - order_by=date
     - Order data by ``event.date`` (ascending)
   * - order_by=-date
     - Order data by ``event.date`` (descending)
   * - order_by=date_last_activity
     - Order data by ``event.date_last_activity`` (ascending)
   * - order_by=-date_last_activity
     - Order data by ``event.date_last_activity`` (descending)

Pagination
~~~~~~~~~~
This API makes use of cursor pagination. Each request will include a ``meta.next`` field containing a URL to fetch the next page of data.

Example:

.. code-block:: text

    # First request
    https://www.commcarehq.org/a/[domain]/api/v0.5/messaging-event/?content_type=sms

    {"objects": [{}, {}, {}...], "meta": {"limit": 20, "next": "https://www.commcarehq.org/a/[domain]/api/v0.5/messaging-event/?cursor=XYZ"}}

    # Request for next page
    https://www.commcarehq.org/a/[domain]/api/v0.5/messaging-event/?cursor=XYZ

    {"objects": [{}, {}, {}...], "meta": {"limit": 20, "next": "https://www.commcarehq.org/a/[domain]/api/v0.5/messaging-event/?cursor=ABC"}}

    # Request for next page
    https://www.commcarehq.org/a/[domain]/api/v0.5/messaging-event/?cursor=ABC

    {"objects": [{}, {}, {}...], "meta": {"limit": 20, "next": null}}

    # "meta.next" is null so there is no more data.

Sample Output
~~~~~~~~~~~~~

.. code-block:: json

    {
      "objects": [
        {
          "id": 10215869,
          "content_type": "email",
          "date": "2020-05-15T04:11:27.482899",
          "case_id": "523132e0-a562-4be1-bbc8-a634423c5c0c",
          "domain": "ny-dev-cdcms",
          "status": "completed",
          "messages": [
            {
              "message_id": 153444,
              "date": "2021-04-13T21:25:26.989",
              "type": "sms",
              "direction": "outgoing",
              "content": "Welcome to CommCare",
              "status": "sent",
              "backend": "MOBILE_BACKEND_TWILIO",
              "phone_number": "+15555993494"
            }
          ],
          "recipient": {
            "recipient_id": "523132e0-a562-4be1-bbc8-a634423c5c0c",
            "type": "case",
            "name": "Mary Little"
          },
          "source": {
            "source_id": "4654",
            "type": "conditional-alert",
            "name": "Email - Welcome Packet"
          }
        }
      ],
      "meta": {
        "limit": 20,
        "next": "https://www.commcarehq.org/a/[domain]/api/v0.5/messaging-event/?cursor=ZGF0ZS5ndGU9MjAyMC0wNS0xN1QyMCUzQTM3JTNBMTEuNzU3OTQwJmxhc3Rfb2JqZWN0X2lkPTEwMjUwOTYw"
      }
    }

Sample API Calls
~~~~~~~~~~~~~~~~

Example of a single filter:

.. code-block:: text

    https://www.commcarehq.org/a/[domain]/api/v0.5/messaging-event/?date.gte=2020-07-13T06:30:21.109409

Example of multiple filters:

.. code-block:: text

    https://www.commcarehq.org/a/[domain]/api/v0.5/messaging-event/?content_type=sms&phone_number=1234567


Messaging Events
================

Summary
-------
To provide users access to the messaging data.

The data in this API is based on a nested data model:

- **Messaging Event**: The core data model representing a messaging event linked to a specific recipient and from a specific source (e.g., Conditional Alert).
- **Message**: The actual message that went to the user.
- A single event may have multiple messages (e.g., SMS surveys which will have one message per interaction with the recipient).

Authentication
--------------
For more information, please review Authentication.

Base URL
--------

.. code-block:: text

    https://www.commcarehq.org/a/[domain]/api/[version]/messaging-event/

Supported versions: ``v0.5``

API Fields and Data Structure
-----------------------------

.. list-table::  **API Fields**
   :widths: 20 40
   :header-rows: 1

   * - Field
     - Note
   * - id
     - Event ID
   * - date
     - Event Date (e.g. 2020-07-13T06:30:21.136197)
   * - date_last_activity
     - Date of the last message activity for this event. Useful for exports since the 'date' field is the date of creation.
   * - domain
     - The Project Space this event belongs to.
   * - content_type
     - Type of the event (e.g. sms, email, sms_survey)
   * - case_id
     - ID of the case if this event is related to one.
   * - status
     - Status of this event (e.g. error, completed, in_progress)

.. list-table:: **Source (Nested Object)**
   :widths: 20 40
   :header-rows: 1

   * - Field
     - Note
   * - type
     - Source type (e.g. broadcast, keyword)
   * - source_id
     - ID of the source
   * - name
     - Name of keyword, broadcast, etc.

.. list-table:: **Recipient (Nested Object)**
   :widths: 20 40
   :header-rows: 1

   * - Field
     - Note
   * - type
     - Recipient type (web_user, case, or mobile_user)
   * - recipient_id
     - Case ID / User ID
   * - name
     - Case name / User name

.. list-table:: **Form (Nested Object)**
   :widths: 20 40
   :header-rows: 1

   * - Field
     - Note
   * - app_id
     - Application ID
   * - form_definition_id
     - Form Definition ID
   * - form_name
     - Name of the form
   * - form_submission_id
     - ID of the submitted form in the case of SMS surveys

.. list-table:: **Error (Nested Object)**
   :widths: 20 40
   :header-rows: 1

   * - Field
     - Note
   * - code
     - Error code
   * - message
     - Display text for the error code
   * - message_detail
     - Additional detail about the error

.. list-table:: **Messages (List of Nested Objects)**
   :widths: 20 40
   :header-rows: 1

   * - Field
     - Note
   * - message_id
     - ID of the message
   * - type
     - "sms" or "email"
   * - direction
     - "incoming" or "outgoing"
   * - content
     - Actual message content that was sent or received
   * - date
     - Message date
   * - date_modified
     - Date of the last modification to the message
   * - status
     - Message status (e.g. error, queued, received, sent)
   * - backend
     - Name of the messaging backend gateway through which the message was sent/received (e.g. Twilio)
   * - error_message
     - Error message in the case of an error
   * - phone_number
     - (only for SMS)
   * - email_address
     - (only for email)
