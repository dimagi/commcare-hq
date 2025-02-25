List Mobile Workers
===================

Overview
--------

**Purpose**
    Get a list of users or a single user. The list of users may be presented to the end user as a simple list of user names, where each name includes a hyperlink to access a list of cases owned by the user.

**Base URL**

.. code-block:: text

    https://www.commcarehq.org/a/[domain]/api/[version]/user/

**Single User URL**

.. code-block:: text

    https://www.commcarehq.org/a/[domain]/api/[version]/user/[user_id]

**Permissions Required**
    Edit Mobile Workers & Edit Access API's


**Authentication and Usage**
    All URL endpoints should be utilized as part of a cURL authentication command. For more information, please review `API Authentication <https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2279637003/CommCare+API+Overview#API-Authentication>`_.

Request & Response Details
--------------------------

**Input Parameters**

.. list-table::
   :header-rows: 1

   * - Name
     - Description
     - Example
   * - ``format``
     - Data format (json by default, xml supported)
     - ``format=xml``
   * - ``group``
     - Group UUID (optional)
     - ``group=ac9d34ff59cf6388e4f5804b12276d8a``
   * - ``archived``
     - List archived users instead of active ones
     - ``archived=true``
   * - ``extras``
     - Adds extra data fields for recent user activity (may slow down API)
     - ``extras=true``

**Output Values**

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
     - ``jdoe@example.commcarehq.org``
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
     - ``[+50253311399, +50253314588]``
   * - ``groups``
     - List of all group IDs belonging to the user
     - ``[9a0accdba29e01a61ea099394737c4fb, b4ccdba29e01a61ea099394737c4fbf7]``
   * - ``primary_location``
     - The location ID of the primary location of the user
     - ``26fc44e2792b4f2fa8ef86178f0a958e``
   * - ``locations``
     - A list of location IDs that the user is assigned to
     - ``[26fc44e2792b4f2fa8ef86178f0a958e, c1b029932ed442a6a846a4ea10e46a78]``
   * - ``user_data``
     - Any additional custom data associated with the user
     - ``{"chw_id": "13/43/DFA"}``
        (If the property begins with a number, it will not be returned when using XML)

**Sample Usage**

.. code-block:: text

    https://www.commcarehq.org/a/demo/api/v0.4/user/?format=xml&limit=5

**Sample JSON Output**

.. code-block:: json

    {
      "meta": {
        "limit": 2,
        "next": null,
        "offset": 0,
        "previous": null,
        "total_count": 29
      },
      "objects": [
        {
          "type": "user",
          "id": "3c5a623af057e23a32ae4000cf291339",
          "username": "jdoe@example.commcarehq.org",
          "first_name": "John",
          "last_name": "Doe",
          "default_phone_number": "+50253311399",
          "email": "jdoe@example.org",
          "phone_numbers": [
            "+50253311399",
            "+50253314588"
          ],
          "groups": [
            "9a0accdba29e01a61ea099394737c4fb",
            "b4ccdba29e01a61ea099394737c4fbf7"
          ],
          "locations": [
            "26fc44e2792b4f2fa8ef86178f0a958e",
            "c1b029932ed442a6a846a4ea10e46a78"
          ],
          "primary_location": "26fc44e2792b4f2fa8ef86178f0a958e",
          "user_data": {
            "chw_id": "13/43/DFA"
          }
        },
        {
          "type": "user",
          "id": "3c5a623af057e23a32ae4000cf2943248",
          "username": "jsmith@example.commcarehq.org",
          "first_name": "Jane",
          "last_name": "Smith",
          "default_phone_number": "+50253311388",
          "email": "jsmith@example.org",
          "phone_numbers": [
            "+50253311388"
          ],
          "locations": [],
          "primary_location": null,
          "groups": [],
          "user_data": {
            "village": "Patna",
            "husband_name": "Bob Smith"
          }
        }
      ]
    }

**Sample XML Output**

.. code-block:: xml

   <response>
       <objects type="list">
           <object id="3c5a623af057e23a32ae4000cf291339">
               <username>jdoe@example.commcarehq.org</username>
               <first_name>John</first_name>
               <last_name>Doe</last_name>
               <default_phone_number>+50253311399</default_phone_number>
               <email>jdoe@example.org</email>
               <phone_numbers type="list">
                   <value>+50253311399</value>
                   <value>+50253314588</value>
               </phone_numbers>
               <groups type="list">
                   <value>9a0accdba29e01a61ea099394737c4fb</value>
                   <value>b4ccdba29e01a61ea099394737c4fbf7</value>
               </groups>
               <user_data type="hash">
                   <chw_id>13/43/DFA</chw_id>
               </user_data>
           </object>
           <object id="3c5a623af057e23a32ae4000cf2943248">
               <username>jsmith@example.commcarehq.org</username>
               <first_name>Jane</first_name>
               <last_name>Smith</last_name>
               <default_phone_number>+50253311388</default_phone_number>
               <email>jsmith@example.org</email>
               <phone_numbers type="list">
                   <value>+50253311388</value>
               </phone_numbers>
               <groups type="list"/>
               <user_data type="hash">
                   <village>Patna</village>
                   <husband_name>Bob Smith</husband_name>
               </user_data>
           </object>
       </objects>
       <meta type="hash">
           <next type="null"/>
           <total_count type="integer">29</total_count>
           <previous type="null"/>
           <limit type="integer">2</limit>
           <offset type="integer">0</offset>
       </meta>
   </response>
