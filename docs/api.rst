.. _api:

===
API
===

For user-facing API documentation, see `API Wiki <https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2143958022/API+Access>`_.

Application Structure API
-------------------------

**Purpose:**
    Retrieve either a specific application or a list of applications for a project, including their module, form, and case schemata. This supports linked applications.

**Base URL:**

.. code-block:: text

    https://www.commcarehq.org/a/[domain]/api/[version]/application/[app_id]
    
*Omit* ``app_id`` *in the URL to retrieve a list of applications.*

**Input Parameters:**

- ``extras``: *(boolean)* If ``true``, includes a dump of application data; otherwise, does not include additional data.

**Output Description:**

The API response includes an ``objects`` field, which is a list of configurations for your applications. Each application object contains:

- ``name``: The name of the application.
- ``version``: The application version (build number).
- ``modules``: A list of modules with:

  - ``case_type``: The case type for the enclosing module.
  - ``case_properties``: A list of all case properties for the case type.
  - ``forms``: A list of all forms in the module.
  - ``questions``: A schema list for each question in the module.

- ``versions``: A list of application versions (builds) created from this application.
- Other application data, if ``extras`` is set to ``true``.

**Sample JSON Output:**

.. code-block:: json

    {
      "meta": {
        "limit": 20,
        "next": null,
        "offset": 0,
        "previous": null,
        "total_count": 4
      },
      "objects": [
        {
          "id": "app uuid",
          "build_on": null,
          "build_comment": null,
          "is_released": false,
          "version": 16,
          "built_from_app_id": null,
          "name": "My application",
          "case_types": {
            "type_of_case_from_app_builder": [
              "case_prop1",
              "case_prop2"
            ]
          },
          "modules": [
            {
              "case_type": "type_of_case_from_app_builder",
              "forms": [
                {
                  "name": {
                    "en": "Name in English",
                    "es": "Nombre en Español"
                  },
                  "questions": [
                    {
                      "label": "The question",
                      "repeat": "",
                      "tag": "input",
                      "value": "/name_in_english/the_question"
                    }
                  ]
                }
              ]
            }
          ],
          "versions": [
            {
              "id": "app version uuid",
              "build_on": "2017-01-30T19:53:20",
              "build_comment": "",
              "is_released": true,
              "version": 16
            }
          ]
        }
      ]
    }

Form Data API
-------------

**Purpose:**
    Retrieve all data associated with a form submission, including all form property values. The form data may be presented to an end user as detailed data associated with a particular case. For example, by clicking on a prenatal visit hyperlink in a case summary screen, the end user may be presented with clinical data associated with a specific prenatal visit.

**Authentication and Usage:**
    All URL endpoints should be used as part of a cURL authentication command. For more information, please review `this <https://dimagi.atlassian.net/wiki/x/LwXKfw>`_.

**Single Form URL:**

.. code-block:: text

    https://www.commcarehq.org/a/[domain]/api/[version]/form/[form_id]/

**Example:**

.. code-block:: text

    https://www.commcarehq.org/a/corpora/api/v0.5/form/66d7a362-18a2-4f45-bd84-06f19b408d64/

**Sample JSON Output:**

.. code-block:: json

    {
      "app_id": "572e968957920fc3e92578988866a5e8",
      "archived": false,
      "build_id": "78698f1516e7d16689e05fce852d1e9c",
      "form": {
        "#type": "data",
        "@name": "Case Update",
        "@uiVersion": "1",
        "@version": "186",
        "@xmlns": "http://openrosa.org/formdesigner/4B1B717C-0CF7-472E-8CC1-1CC0C45AA5E0",
        "case": {
          "@case_id": "8f8fd909-684f-402d-a892-f50e607fffef",
          "@date_modified": "2012-09-29T19:10:00",
          "@user_id": "f4c63df2ef7f9da2f93cab12dc9ef53c",
          "@xmlns": "http://commcarehq.org/case/transaction/v2",
          "update": {
            "data_node": "55",
            "dateval": "2012-09-26",
            "geodata": "5.0 5.0 5.0 5.0",
            "intval": "5",
            "multiselect": "b",
            "singleselect": "b",
            "text": "TEST"
          }
        },
        "meta": {
          "@xmlns": "http://openrosa.org/jr/xforms",
          "deviceID": "0LRGVM4SFN2VHCOVWOVC07KQX",
          "instanceID": "00460026-a33b-4c6b-a4b6-c47117048557",
          "timeEnd": "2012-09-29T19:10:00",
          "timeStart": "2012-09-29T19:08:46",
          "userID": "f4c63df2ef7f9da2f93cab12dc9ef53c",
          "username": "afrisis"
        }
      },
      "id": "00460026-a33b-4c6b-a4b6-c47117048557",
      "received_on": "2012-09-29T17:24:52",
      "type": "data",
      "uiversion": "1",
      "version": "186"
    }



Bulk User Resource
~~~~~~~~~~~~~~~~~~
| Resource name: ``bulk_user``
| First version available: ``v0.5``

This resource is used to get basic user data in bulk, fast.  This is especially useful if you need to get, say, the name and phone number of every user in your domain for a widget.

Currently, the default fields returned are::

    id
    email
    username
    first_name
    last_name
    phone_numbers

Supported Parameters:
.....................

 * ``q`` - query string
 * ``limit`` - maximum number of results returned
 * ``offset`` - Use with ``limit`` to paginate results
 * ``fields`` - restrict the fields returned to a specified set

Example query string::

    ?q=foo&fields=username&fields=first_name&fields=last_name&limit=100&offset=200

This will return the first and last names and usernames of users matching the query "foo".  This request is for the third page of results (200-300) 

| Additional notes:
| It is simple to add more fields if there arises a significant use case.
| Potential future plans:
    Support filtering in addition to querying.
    Support different types of querying.
    Add an order_by option

List Cases (Version 3+)
-----------------------

**Purpose:**
    Retrieves a list of cases. The list of cases may be presented to the end user as a simple list of cases, where each case name incudes a hyperlink to access detailed information about the case.

**Base URL:**

.. code-block:: text

    https://www.commcarehq.org/a/[domain]/api/v0.5/case/

**Authentication:**
    For more information, please review `this <https://dimagi.atlassian.net/wiki/x/LwXKfw>`_.

**Input Parameters:**

In addition to all `Case Data API <https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2143957360>`_. parameters, you may use the following input parameters to filter results and control paging:

.. list-table::
   :header-rows: 1

   * - Name
     - Description
     - Example
     - Summary
   * - ``owner_id``
     - User or Group UUID (optional)
     - ``owner_id=ac9d34ff59cf6388e4f5804b12276d8a``
     - All cases owned by that entity (should not use with user)
   * - ``user_id``
     - User UUID (optional)
     - ``user_id=3c5a623af057e23a32ae4000cf291339``
     - All cases last modified by that user
   * - ``type``
     - Type of case (optional)
     - ``type=pregnant_mother``
     - All cases matching the type
   * - ``closed``
     - Case status (optional)
     - ``closed=true``
     - All open/closed/both cases
   * - ``indexed_on_start``
     - A date (and time). Will return only cases that have had data modified since the passed-in date.
     - ``indexed_on_start=2021-01-01``  
       ``indexed_on_start=2021-01-01T06:05:42``
     - This is the recommended field to use for data pagination.  
       It is very similar to server_date_modified but handles edge cases better.
   * - ``indexed_on_end``
     - A date (and time). Will return only cases that have had data modified before the passed-in date.
     - ``indexed_on_end=2021-01-01``  
       ``indexed_on_end=2021-01-01T06:05:42``
     - Filters cases modified before this date.
   * - ``date_modified_start``
     - Modified after this date (phone date)
     - ``date_modified_start=2012-05-20``  
       ``date_modified_start=2013-09-29T10:40Z``
     - Defaults to the first submission date.
   * - ``date_modified_end``
     - Modified before this date (phone date)
     - ``date_modified_end=2012-05-27``
     - Defaults to the current date.
   * - ``server_date_modified_start``
     - Modified after this date (server date)
     - ``server_date_modified_start=2012-05-20``
     - Defaults to the first submission date.
   * - ``server_date_modified_end``
     - Modified before this date (server date)
     - ``server_date_modified_end=2012-05-27``
     - Defaults to the current date.
   * - ``name``
     - Name
     - ``name=NEAL``
     - Case name used for filtering.
   * - ``limit``
     - The maximum number of records to return.
     - ``limit=100``
     - Defaults to 20. Maximum is 5000.
   * - ``offset``
     - The number of records to offset in the results.
     - ``offset=100``
     - Defaults to 0.
   * - ``external_id``
     - 'external_id' property
     - ``external_id=123abc``
     - Used to filter cases by external ID.
   * - ``indexed_on``
     - Indexed on date
     - ``order_by=indexed_on``
     - Defaults to the oldest indexed_on date.
   * - ``server_date_modified``
     - Date after which case was modified on the server
     - ``order_by=server_date_modified``
     - Defaults to oldest server_date_modified.


**Output Values:**

.. list-table::
   :header-rows: 1

   * - Name
     - Description
     - Example
   * - ``case_id``
     - Case UUID
     - ``0X9OCW3JMV98EYOVN32SGN4II``
   * - ``username``
     - User name of case owner, including domain
     - ``jdoe@example.commcarehq.org``
   * - ``user_id``
     - UUID user that owns the case
     - ``3c5a623af057e23a32ae4000cf291339``
   * - ``owner_id``
     - UUID group/user that owns the case
     - ``ac9d34ff59cf6388e4f5804b12276d8a``
   * - ``case_name``
     - Name of case
     - ``Rose``
   * - ``external_id``
     - External ID associated with the case
     - ``123456``
   * - ``case_type``
     - Type of case
     - ``pregnant_mother``
   * - ``date_opened``
     - Date and time case was opened
     - ``2011-11-16T14:26:15Z``
   * - ``date_modified``
     - Date and time case was last modified
     - ``2011-12-13T15:09:47Z``
   * - ``closed``
     - Case status
     - ``false``
   * - ``date_closed``
     - Date and time case was closed
     - ``2011-12-20T15:09:47Z``

**Sample Usage:**

.. code-block:: text

    https://www.commcarehq.org/a/[domain]/api/v0.5/case/?format=xml

**Sample XML Output:**

.. code-block:: xml

    <cases>
        <case>
            <case_id>0X9OCW3JMV98EYOVN32SGN4II</case_id>
            <username>jdoe@example.commcarehq.org</username>
            <user_id>3c5a623af057e23a32ae4000cf291339</user_id>
            <owner_id>3c5a623af057e23a32ae4000cf291339</owner_id>
            <case_name>Rose</case_name>
            <external_id>123456</external_id>
            <case_type>pregnancy</case_type>
            <date_opened>2011-11-16T14:26:15</date_opened>
            <date_modified>2011-12-13 15:09:47</date_modified>
            <closed>false</closed>
            <date_closed>2011-12-20 15:09:47</date_closed>
        </case>
    </cases>

**Sample JSON Output:**

.. code-block:: json

    [
      {
        "case_id": "45WKYXQRFFU3AT4Y022EX7HF2",
        "closed": false,
        "date_closed": null,
        "date_modified": "2012-03-13T18:21:52Z",
        "domain": "demo",
        "properties": {
          "case_name": "ryan",
          "case_type": "programmer",
          "date_opened": "2012-03-13T18:21:52Z",
          "external_id": "45WKYXQRFFU3AT4Y022EX7HF2"
        }
      }
    ]

List Forms
----------

**Purpose:**
    Get a list of form submissions.

**Base URL:**

.. code-block:: text

    https://www.commcarehq.org/a/[domain]/api/v0.5/form/

**Authentication:**
    For more information, please review `API Authentication <https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2279637003/CommCare+API+Overview#API-Authentication>`_.

**Input Parameters:**

The forms can be filtered using the following parameters, which also control paging of the output records.

.. list-table::
   :header-rows: 1

   * - Name
     - Description
     - Example
   * - ``xmlns``
     - Form XML namespace (optional)
     - ``xmlns=http://openrosa.org/formdesigner/dd3190c7dd7e9e7d469a9705709f2f6b4e27f1d8``
   * - ``limit``
     - The maximum number of records to return. Default: 20. Maximum: 1000
     - ``limit=100``
   * - ``offset``
     - The number of records to offset in the results. Default: 0.
     - ``offset=100``
   * - ``indexed_on_start``
     - A date (and time). Will return only forms that have had data modified since the passed in date.
     - ``indexed_on_start=2021-01-01T06:05:42``
   * - ``indexed_on_end``
     - A date (and time). Will return only forms that have had data modified before the passed in date.
     - ``indexed_on_end=2021-01-01T06:05:42``
   * - ``received_on_start``
     - A date (and time). Will return only forms that were received after the passed in date.
     - ``received_on_start=2012-01-01T06:05:42``
   * - ``received_on_end``
     - A date (and time). Will return only forms that were received before the passed in date.
     - ``received_on_end=2013-11-25T06:05:42``
   * - ``appVersion``
     - The exact version of the CommCare application used to submit the form.
     - ``appVersion=v2.6.1%20(3b8ee4...)``
   * - ``include_archived``
     - When set to 'true' archived forms will be included in the response.
     - ``include_archived=true``
   * - ``app_id``
     - The returned records will be limited to the application defined.
     - ``app_id=02bf50ab803a89ea4963799362874f0c``
   * - ``indexed_on``
     - The returned records will be ordered according to indexed_on date, starting from the oldest date.
     - ``order_by=indexed_on``
   * - ``server_modified_on``
     - The returned records will be ordered according to server_modified_on date, starting from the oldest date.
     - ``order_by=server_modified_on``
   * - ``received_on``
     - The returned records will be ordered according to server received_on date, starting from the oldest date.
     - ``order_by=received_on``
   * - ``case_id``
     - A case UUID. Will only return forms which updated that case.
     - ``case_id=4cf7736e-2cc7-4d46-88e3-4b288b403362``

**Sample Usage:**

.. code-block:: text

    https://www.commcarehq.org/a/[domain]/api/v0.5/form/

**Sample JSON Output:**

.. code-block:: json

    {
      "meta": {
        "limit": 20,
        "next": "/a/corpora/api/v0.5/form/?limit=20&offset=20",
        "offset": 0,
        "previous": null,
        "total_count": 6909
      },
      "objects": [
        {
          "app_id": "effb341b",
          "archived": false,
          "build_id": "e0a6125",
          "domain": "my-project",
          "id": "f959449c-8776-42ac-b776-3f564fafc331",
          "received_on": "2016-11-29T14:50:42.530616Z",
          "type": "data",
          "version": "18"
        }
      ]
    }

Location API
------------

The Location API is available from version v0.5. Version v0.5 is read-only. It allows you to list locations and get location details.

Version v0.6 has the same read-only list and details endpoints as v0.5 with just a few updates and adds the ability to create and update locations, one at a time or in bulk.

List Locations
-------------

**Base URL:**

.. code-block:: text

    GET https://www.commcarehq.org/a/[domain]/api/[version]/location/

**Input Parameters:**

v0.5 Locations can be filtered by the following attributes as request parameters:

.. list-table::
   :header-rows: 1

   * - Name
     - Description
   * - ``site_code``
     - Site code for the location
   * - ``external_id``
     - External identifier for the location
   * - ``created_at``
     - Timestamp when the location was created
   * - ``last_modified``
     - Timestamp of the last modification
   * - ``latitude``
     - Latitude coordinate of the location
   * - ``longitude``
     - Longitude coordinate of the location

**Sample JSON Output (v0.5):**

.. code-block:: json

    {
      "meta": {
        "limit": 20,
        "next": null,
        "offset": 0,
        "previous": null,
        "total_count": 2
      },
      "objects": [
        {
          "created_at": "2023-05-09T16:10:47.225938",
          "domain": "[domain]",
          "external_id": null,
          "id": 1,
          "last_modified": "2023-05-09T16:10:47.225947",
          "latitude": null,
          "location_data": {},
          "location_id": "f373a6837c1243938abfc56618cce88b",
          "location_type": "https://www.commcarehq.org/a/[domain]/api/v0.5/location_type/1/",
          "longitude": null,
          "name": "Namibia",
          "parent": null,
          "resource_uri": "https://www.commcarehq.org/a/[domain]/api/v0.5/location/f373a6837c1243938abfc56618cce88b/",
          "site_code": "namibia"
        }
      ]
    }

**v0.6**

The main distinctions between the v0.5 and v0.6 GET endpoints are that v0.6:

- Removes a few fields and adds a few fields from the response (there is no ``external_id`` with v0.6, for example, but there is ``parent_location_id``).
- Currently does not allow filtering on the list endpoint.

For the list endpoint, the "meta" section will look the same and the locations will still be in a list called "objects". But an individual location object will look like:

.. code-block:: json

    {
        "domain": "dimagi-test",
        "last_modified": "2024-03-11T19:29:16.845849",
        "latitude": "31.4100000000",
        "location_data": {
            "pop": "1001"
        },
        "location_id": "68e65fbc2dc840ff8bf03849e57aca88",
        "location_type_code": "county",
        "location_type_name": "County",
        "longitude": null,
        "name": "Fairfax County",
        "parent_location_id": "41b0bdfbae20428e9435ae8c3dcd22e7",
        "site_code": "fairfax_county"
    }

Also notice how compared to v0.5, the v0.6 location data has just the ``location_id``, no resource URL.

Location Details
----------------

**Base URL:**

.. code-block:: text

    GET https://www.commcarehq.org/a/[domain]/api/[version]/location/[location_id]

**Sample JSON Output (v0.5):**

.. code-block:: json

    {
      "created_at": "2023-05-09T16:10:47.225938",
      "domain": "[domain]",
      "external_id": null,
      "id": 1,
      "last_modified": "2023-05-09T16:10:47.225947",
      "latitude": null,
      "location_data": {},
      "location_id": "f373a6837c1243938abfc56618cce88b",
      "location_type": "https://www.commcarehq.org/a/[domain]/api/v0.5/location_type/1/",
      "longitude": null,
      "name": "Namibia",
      "parent": null,
      "resource_uri": "https://www.commcarehq.org/a/[domain]/api/v0.5/location/f373a6837c1243938abfc56618cce88b/",
      "site_code": "namibia"
    }

**v0.6**

You can get the details for an individual location using v0.6 as well. See the v0.6 section of the list documentation above for information on what single location object serialization looks like in v0.6.

Create Location (Individual)
----------------------------

**Base URL:**

.. code-block:: text

    POST https://www.commcarehq.org/a/[domain]/api/[version]/location/

**Description:**

Create an individual location. Available from version v0.6.

**Required Fields:**

- ``name``
- ``location_type_code``

**Other Fields (Optional):**

.. list-table::
   :header-rows: 1

   * - Field
     - Description
   * - ``site_code``
     - The system will generate one if not provided. Must be unique on the domain.
   * - ``latitude``
     - Latitude coordinate of the location.
   * - ``longitude``
     - Longitude coordinate of the location.
   * - ``location_data``
     - JSON dictionary instead of a string.
   * - ``parent_location_id``
     - The ID will be validated to ensure the parent exists, supports child locations, and has no duplicate names.

**Example Request Body:**

.. code-block:: json

    {
        "latitude": "31.41",
        "location_data": {
            "pop": "1000"
        },
        "location_type_code": "city",
        "longitude": null,
        "name": "Greenville",
        "parent_location_id": "46329a9e1bad47158739d56f6f667165"
    }

Update Location (Individual)
---------------------------

**Base URL:**

.. code-block:: text

    PUT https://www.commcarehq.org/a/[domain]/api/[version]/location/[location_id]

**Description:**

Allows editing an individual location. Available from version v0.6.

**Editable Fields:**

.. list-table::
   :header-rows: 1

   * - Field
     - Description
   * - ``name``
     - Must be unique among siblings.
   * - ``site_code``
     - Must be unique on the domain.
   * - ``latitude``
     - Latitude coordinate of the location.
   * - ``longitude``
     - Longitude coordinate of the location.
   * - ``location_data``
     - Dictionary format.
   * - ``location_type_code``
     - If the location has a parent, the new location type must be a valid child type of that parent.
   * - ``parent_location_id``
     - The parent must exist, be able to have child locations of this type, and must not already have a child with the same name.

If a part of the location’s update fails due to invalid fields, the update will not occur at all.If you wanted to update the location type and parent for the location, an example request body would be - 

**Example Request Body:**

.. code-block:: json

    {
        "location_type_code": "county",
        "parent_location_id": "46329a9e1bad47158739d56f6f667165"
    }
### Create and Update Locations (in Bulk)

**Base URL:**

.. code-block:: text

    PATCH https://www.commcarehq.org/a/[domain]/api/[version]/location/

**Description:**

Version v0.6 allows you to create and update locations in bulk. Even though the method is PATCH, you can also create locations as well as update using this method.

The request body should be a list of locations, with each location as a JSON dictionary (if you are using JSON). The list should be called "objects". Include ``location_id`` in the dictionary if you want to update a location, and don’t include it if you want to create a location.

When creating a location via this method, the API uses the same validation as the create endpoint. For updating, it uses the same validation as the update endpoint. For updating a location, see the table of allowed fields in the documentation for "Update". For creating, see the table of fields under "Create Location".

**Example Request Body:**

.. code-block:: json

    {
        "objects": [
            {
                "name": "Newtown",
                "latitude": "31.41",
                "location_data": {
                    "pop": "1001"
                },
                "location_type_code": "city",
                "longitude": null,
                "parent_location_id": "46329a9e1bad47158739d56f6f667165"
            },
            {
                "location_id": "eea759ae08044807be749f665a1fd39a",
                "name": "Springfield",
                "latitude": "32.42",
                "location_data": {
                    "pop": "1004"
                }
            }
        ]
    }

With this request body, the first dictionary will create a location called "Newtown", and update a location with the ID ``eea759ae08044807be749f665a1fd39a`` to have the name "Springfield".

Lastly, the PATCH request is atomic. Meaning if validation fails for a single location in the request, none of the locations will be created or updated.

List Location Types
-------------------

**Base URL:**

.. code-block:: text

    GET https://www.commcarehq.org/a/[domain]/api/[version]/location_type/

**Description:**

Retrieves a list of location types available in the specified domain.

**Sample JSON Output:**

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
          "resource_uri": "https://www.commcarehq.org/a/[domain]/api/v0.5/location_type/1/",
          "shares_cases": false,
          "view_descendants": false
        }
      ]
    }

Location Type Details
---------------------

**Base URL:**

.. code-block:: text

    GET https://www.commcarehq.org/a/[domain]/api/[version]/location_type/[id]

**Description:**

Retrieves details for a specific location type.

**Sample JSON Output:**

.. code-block:: json

    {
      "administrative": true,
      "code": "country",
      "domain": "[domain]",
      "id": 1,
      "name": "Country",
      "parent": null,
      "resource_uri": "https://www.commcarehq.org/a/[domain]/api/v0.5/location_type/1/",
      "shares_cases": false,
      "view_descendants": false
    }



