Case Data API v2
================

Major changes from v1
---------------------

1. Introduces straightforward, JSON-based case creations and
   modifications, individually and in bulk.  Previously this was only
   possible by constructing XForms, a complex XML document structure.
2. Allows for filtering and querying cases by project-specific case
   properties, not just metadata.
3. Introduces a bulk get-by-id and get-by-external-id endpoint.
4. Clearer serialization format that’s more in-line with commonly used
   terminology elsewhere on HQ.
5. Performant deep pagination at scale.  This makes it more suitable for
   fetching very large data sets, such as for populating an analytics
   database.


Supported Endpoints and Methods
-------------------------------

All endpoints are available under
``www.commcarehq.org/a/<domain>/api/case/v2/``

=========================== ======================================
**Endpoint**                **Description**
GET /                       Query list of cases
GET /<case_id>              Get individual case
GET /<case_id>,<case_id>... Get multiple cases by ID
POST /bulk-fetch/           Get cases in bulk by ID or external ID
POST /                      Create new case
POST /                      Create or update cases in bulk
PUT /<case_id>              Update existing case
PUT /                       Update existing case by external ID
=========================== ======================================

Single Case Serialization Format
--------------------------------

Below is the return format for an individual case. It is used by each of
the supported endpoints.

.. code-block:: json

    {
      "domain": "queens-gambit",
      "case_id": "79e25a30-8db5-4a5a-827b-0297b254e87f",
      "case_type": "patient",
      "case_name": "Elizabeth Harmon",
      "external_id": "1",
      "owner_id": "20cc9dda-b90a-4af3-aa3d-fc67184e73ef",
      "date_opened": "2020-03-19T14:31:34.133000Z",
      "last_modified": "2020-03-19T14:31:34.133000Z",
      "server_last_modified": "2020-03-19T14:31:34.133000Z",
      "indexed_on": "2020-03-19T14:31:34.133000Z",
      "closed": false,
      "date_closed": null,
      "properties": {
        "dob": "1948-11-02"
      },
      "indices": {
        "parent": {
          "case_id": "eb1a8c23-6d6d-4b61-894c-ae1c437d8dac",
          "case_type": "household",
          "relationship": "child"
        }
      }
    }


**Included fields**

+-----------------------------+---------------------------------------+
| **Field Name**              | **Description**                       |
+-----------------------------+---------------------------------------+
| domain                      |                                       |
+-----------------------------+---------------------------------------+
| case_id                     |                                       |
+-----------------------------+---------------------------------------+
| case_type                   |                                       |
+-----------------------------+---------------------------------------+
| case_name                   |                                       |
+-----------------------------+---------------------------------------+
| external_id                 |                                       |
+-----------------------------+---------------------------------------+
| owner_id                    |                                       |
+-----------------------------+---------------------------------------+
| date_opened                 | ISO 8601 UTC datetime                 |
+-----------------------------+---------------------------------------+
| last_modified               | ISO 8601 UTC datetime                 |
+-----------------------------+---------------------------------------+
| server_last_modified        | ISO 8601 UTC datetime                 |
+-----------------------------+---------------------------------------+
| indexed_on                  | ISO 8601 UTC datetime                 |
|                             |                                       |
|                             | This represents the time the case was |
|                             | most recently indexed for use in the  |
|                             | API.  This field is used in           |
|                             | paginating the API results.  It is    |
|                             | subject to change without notice from |
|                             | regular maintenance operations.  When |
|                             | returned from in the response to a    |
|                             | create or update request, it          |
|                             | represents the time the response was  |
|                             | processed, as it hasn’t yet been      |
|                             | indexed.                              |
+-----------------------------+---------------------------------------+
| closed                      | Boolean true or false.  Always        |
|                             | present                               |
+-----------------------------+---------------------------------------+
| date_closed                 | ISO 8601 UTC datetime.  Field is      |
|                             | always present, but null for open     |
|                             | cases.                                |
+-----------------------------+---------------------------------------+
| properties                  | Contains all user-defined properties, |
|                             | represented as strings.               |
+-----------------------------+---------------------------------------+
| indices                     | Dict containing a series of indices   |
|                             | (not included by default)             |
+-----------------------------+---------------------------------------+
| indices.<name>              | User-provided name for an index,      |
|                             | typically “parent” or “host”, but not |
|                             | constrained                           |
+-----------------------------+---------------------------------------+
| indices.<name>.case_id      |                                       |
+-----------------------------+---------------------------------------+
| indices.<name>.case_type    |                                       |
+-----------------------------+---------------------------------------+
| indices.<name>.relationship | Either “child” or “extension”         |
+-----------------------------+---------------------------------------+

Case Create / Update Format
---------------------------

Below is the format expected by the PUT and POST endpoints when creating
or updating a case.

.. code-block:: json

    {
      "case_id": "5160d95d-efdc-4fbb-ba11-5f5bccdde950",
      "case_type": "patient",
      "case_name": "Elizabeth Harmon",
      "owner_id": "20cc9dda-b90a-4af3-aa3d-fc67184e73ef",
      "temporary_id": "1",
      "external_id": "1",
      "properties": {
        "dob": "1948-11-02"
      },
      "indices": {
        "parent": {
          "case_id": "eb1a8c23-6d6d-4b61-894c-ae1c437d8dac",
          "case_type": "household",
          "relationship": "child"
        }
      }
    }

**Included Fields**

**Note**: All values other than close must be string types, including
property values.

+-----------------------------+---------------------------------------+
| **Field Name**              | **Description**                       |
+-----------------------------+---------------------------------------+
| case_id                     | Only allowed in bulk updates.  Will   |
|                             | be server generated for case          |
|                             | creations,                            |
|                             | and passed in as part of the resource |
|                             | URI for individual updates            |
+-----------------------------+---------------------------------------+
| case_type                   | Required for new cases, optional for  |
|                             | updates.  Max length 255 characters.  |
+-----------------------------+---------------------------------------+
| case_name                   | Required for new cases, optional for  |
|                             | updates.  Max length 255 characters.  |
+-----------------------------+---------------------------------------+
| owner_id                    | UUID of the case owner.  Not          |
|                             | validated server-side.  Required for  |
|                             | new cases, optional for updates.  Max |
|                             | length 255 characters.                |
+-----------------------------+---------------------------------------+
| temporary_id                | Bulk create/update only.  Must be     |
|                             | unique per request.  Other cases may  |
|                             | reference this ID in index            |
|                             | definitions.  Not saved.              |
+-----------------------------+---------------------------------------+
| external_id                 | Max length 255 characters             |
+-----------------------------+---------------------------------------+
| properties                  | Enumeration of property_name / value  |
|                             | pairs.  All user-defined.  All values |
|                             | must be strings, and all property     |
|                             | names must be valid XML element       |
|                             | names, meaning:                       |
|                             |                                       |
|                             | -  Not blank                          |
|                             | -  Contains only letters and numbers  |
|                             | -  Doesn’t start with a number        |
|                             | -  Doesn’t start with “xml”           |
+-----------------------------+---------------------------------------+
| indices                     | Dict containing a series of indices   |
+-----------------------------+---------------------------------------+
| indices.<name>              | User-provided name for an index,      |
|                             | typically “parent” or “host”, but not |
|                             | constrained. Like property names,     |
|                             | this must be a valid XML element      |
|                             | name.                                 |
+-----------------------------+---------------------------------------+
| indices.<name>.case_id      |                                       |
+-----------------------------+---------------------------------------+
| indices.<name>.temporary_id | Bulk create/update only.  Can be used |
|                             | in lieu of providing a case_id in     |
|                             | instances where the referenced case   |
|                             | is also created in the same request.  |
+-----------------------------+---------------------------------------+
| indices.<name>.case_type    |                                       |
+-----------------------------+---------------------------------------+
| indices.<name>.relationship | Must be either “child” or             |
|                             | “extension”. See the `Extension       |
|                             | Cas                                   |
|                             | es <https://dimagi-dev.atlassian.net/ |
|                             | wiki/display/saas/Extension+Cases>`__ |
|                             | feature flag.                         |
+-----------------------------+---------------------------------------+
| close                       | Boolean True or False, defaults to    |
|                             | False                                 |
+-----------------------------+---------------------------------------+

API Usage
---------

Get List of Cases
~~~~~~~~~~~~~~~~~

Interface - ``GET /a/<domain>/api/case/v2/``

This endpoint returns a list of cases, which can be filtered as
described below.

+----------------------------------+----------------------------------+
| **Filter Param**                 | **Description**                  |
+----------------------------------+----------------------------------+
| limit                            | Defaults to 20, maximum 5000     |
+----------------------------------+----------------------------------+
| external_id                      |                                  |
+----------------------------------+----------------------------------+
| case_type                        |                                  |
+----------------------------------+----------------------------------+
| owner_id                         |                                  |
+----------------------------------+----------------------------------+
| case_name                        |                                  |
+----------------------------------+----------------------------------+
| closed                           | Boolean true or false            |
+----------------------------------+----------------------------------+
| | Indices.parent                 | id of a parent or host case (or  |
| | indices.host                   | other type).  Will return        |
|                                  | children/extensions of that case |
| indices.<name>                   |                                  |
+----------------------------------+----------------------------------+
| last_modified.gt /               | Accepts ISO 8601 date or         |
| last_modified.gte /              | datetime values                  |
| last_modified.lt /               |                                  |
| last_modified.lte                |                                  |
+----------------------------------+----------------------------------+
| server_last_modified.gt (and     | Accepts ISO 8601 date or         |
| gte, lt, lte)                    | datetime values                  |
+----------------------------------+----------------------------------+
| indexed_on.gt (and gte, lt, lte) | Accepts ISO 8601 date or         |
|                                  | datetime values                  |
+----------------------------------+----------------------------------+
| date_opened.gt (gte, lte, lt)    | Accepts ISO 8601 date or         |
|                                  | datetime values                  |
+----------------------------------+----------------------------------+
| date_closed.gt (gte, lte, lt)    | Accepts ISO 8601 date or         |
|                                  | datetime values                  |
+----------------------------------+----------------------------------+
| properties.<property> (eg:       | User-defined case properties.    |
| “properties.state”)              | This supports only exact matches |
|                                  | like “properties.state=bihar” or |
|                                  | “properties.is_testing=false”.   |
|                                  | Empty values and missing values  |
|                                  | are treated the same, so         |
|                                  | “properties.state=” will match   |
|                                  | cases where state isn’t set, and |
|                                  | those where it’s set to the      |
|                                  | empty string.                    |
+----------------------------------+----------------------------------+

Return value is a list of cases, each serialized as described in
"`Single Case Serialization Format`_".


Pagination
~~~~~~~~~~

While most other CommCare APIs use limit and offset for pagination, this
doesn’t work well when pulling large data sets, as performance suffers
the deeper you page. To better support pulling large datasets, this API
uses what’s called “cursor pagination”.  If there is more than one page
of results, the response from this API includes a “next” link, which can
be followed to get the next page of results.  When iterated through in
this way, you should obtain a complete set of results, ordered from
oldest to newest.

If any cases are updated during the data pull, they may appear again
towards the end of the results set.

Get individual case
~~~~~~~~~~~~~~~~~~~

Interface - ``GET /a/<domain>/api/case/v2/<case_id>``

This API takes no additional parameters.  The return value is a single
case serialized as described in "`Single Case Serialization Format`_".

Get Case's index information (parent/child or host/extension)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Interface - ``GET /a/<domain>/api/case/v2/?indices.parent=<parent_case_id>``

Indices are included in the serialization of individual cases, so to
find a case’s parent, you need only look at indices.parent.case_id in
the case itself.

To access “reverse” indices, you can use the list view with an index
filter.  For example, to identify children of a household case, you can
run a query to find cases which have a parent index pointing to that
household case’s ID.

Response format

.. code-block:: json

    {
      "matching_records": 1,
      "cases": [
        {
          "domain": "queens-gambit",
          "case_id": "1",
          "case_type": "assignment",
          "case_name": "assignment",
          "external_id": "1",
          "owner_id": "1",
          "date_opened": "2021-01-18T18:24:23.480723Z",
          "last_modified": "2021-01-18T18:24:23.480723Z",
          "server_last_modified": "2021-01-18T19:52:37.516558Z",
          "indexed_on": "2021-01-18T19:55:13.707193Z",
          "closed": false,
          "date_closed": null,
          "properties": {
            "assignment_type": "primary"
          },
          "indices": {
            "parent": {
              "case_id": "1",
              "case_type": "contact",
              "relationship": "extension"
            }
          }
        }
      ]
    }

Get cases in bulk
~~~~~~~~~~~~~~~~~

1. GET request using Case IDs
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Interface - ``GET /a/<domain>/api/case/v2/<case_id>,<case_id>,<case_id>``

Limitations
~~~~~~~~~~~

The number of cases that can be fetched in this way is limited by the
maximum URL length making it unsuitable for fetching more than
approximately 100 cases. To fetch more cases use the bulk fetch
endpoint.

2. POST request using Case IDs or External IDs
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Interface - ``POST /a/<domain>/api/case/v2/bulk_fetch/``

A more flexible approach to fetching cases in bulk is to use a POST
request where the case IDs are supplied in the POST body.  You may also
specify external IDs in this way.

Body must have one or both of the ‘case_id’, ‘external_id’ fields.

.. code-block:: json

    {
      "case_id": [
        "30ad22bd-f828-4e3f-8287-a67a180cff4f",
        "d5e5962a-c5f1-483c-a58a-590167d594a9"
      ],
      "external_id": [
        "id1",
        "id2"
      ]
    }

**Note**: This endpoint allows you to pull data about specific cases by
ID or external ID.

Response format (cases truncated for clarity)

.. code-block:: json

    {
      "matching_records": 2,
      "missing_records": 2,
      "cases": [
        {"case_id": "30ad22bd-f828-4e3f-8287-a67a180cff4f", "properties": {"dob": "1980-08-20"}},
        {"case_id": "d5e5962a-c5f1-483c-a58a-590167d594a9", "error": "not found"},
        {"external_id": "id1", "error": "not found"},
        {"case_id": "5262c03f-f483-4b36-9a08-cdaf89791e65", "external_id": "id2"},
      ]
    }

+--------------------+------------------------------------------------+
| **Response field** | **Description**                                |
+--------------------+------------------------------------------------+
| matching_records   | The number of cases that were found            |
+--------------------+------------------------------------------------+
| missing_records    | The number of cases that were not found        |
+--------------------+------------------------------------------------+
| cases              | The list of serialized cases. The cases in     |
|                    | this list will be in the same order as the     |
|                    | provided IDs. If a case was not found a stub   |
|                    | record will be included in the results as      |
|                    | shown above.                                   |
|                    |                                                |
|                    | If both case IDs and external IDs are supplied |
|                    | in the request body then the response will     |
|                    | include both sets appended in the same list    |
|                    | (cases fetched by ‘case_id’ first followed by  |
|                    | cases fetched by ‘external_id’.                |
+--------------------+------------------------------------------------+

Create Case
~~~~~~~~~~~

Interface - ``POST /a/<domain>/api/case/v2/``

The body of the request should contain the case update format described
in "`Case Create / Update Format`_"

Return value includes two fields:

========= ===========================================
**Param** **Description**
xform_id  ID of the form generated to create the case
case      Serialized version of the case
========= ===========================================

This response includes the current state of the case after the creation
(or update) has been provided.  Note that if you attempt to immediately
fetch the case anyways, there may be a slight delay before the update is
available.

Update Existing Case
~~~~~~~~~~~~~~~~~~~~

Interface - ``PUT /a/<domain>/api/case/v2/<case_id>``

The body of the request should contain the case update format described
in "`Case Create / Update Format`_"

Return value includes two fields:

========= ===============================================
**Param** **Description**
xform_id  ID of the form generated to update the case
case      Serialized version of the new state of the case
========= ===============================================

Bulk Create/Update Cases
~~~~~~~~~~~~~~~~~~~~~~~~

Interface - ``POST /a/<domain>/api/case/v2/``

The body of the request should contain a list of case updates in the
format described in "`Case Create / Update Format`_".

In addition to those fields, **this endpoint also requires that each
update include a “create” field set to either true or false.**  This is
used to determine whether it is a case creation or update.

The response contains:

========= =========================================================
**Param** **Description**
xform_id  ID of the (single) form generated to update all cases
cases     Serialized version of the new state of the cases provided
========= =========================================================

.. _limitations-1:

Limitations
~~~~~~~~~~~

The bulk API will allow users to create or modify up to 100 cases in a
single request.  These will all be created in a single form submission.

If more than 100 cases are submitted, the server will return a 400
“Payload too large” response, without saving any changes.

Temporary Id
^^^^^^^^^^^^

Case indices can be created using either case_id, external_id, or
“temporary_id”.  This “temporary_id” will not be stored and exists only
during the processing of the request - it’s useful for creating both a
case and its child in the same request, in situations where case_id and
external_id are not suitable.

Example using temporary ID:

.. code-block:: json

    [
      {
        "create": true,
        "case_type": "mother",
        "case_name": "Cersei Lannister",
        "owner_id": "20cc9dda-b90a-4af3-aa3d-fc67184e73ef",
        "temporary_id": "1",
        "properties": {
          "dob": "1988-11-02"
        }
      },
      {
        "create": true,
        "case_type": "baby",
        "case_name": "Tommen Baratheon",
        "owner_id": "9dd08c69-4ace-4e1d-9929-146d22d1070c",
        "properties": {
          "dob": "2008-03-01"
        },
        "indices": {
          "parent": {
            "temporary_id": "1",
            "case_type": "mother",
            "relationship": "child"
          }
        }
      }
    ]


Form Submission
---------------

All case creations and updates will happen by submitting an XForm
generated on the server.  Here are some notable parameters associated
with that:

+--------------------+------------------------------------------------+
| **Param**          | **Description**                                |
+--------------------+------------------------------------------------+
| username / user_id | Corresponding to the user who submitted the    |
|                    | request.  The API cannot not be used to make   |
|                    | it appear that another user made case updates. |
+--------------------+------------------------------------------------+
| xmlns              | http://commcarehq.org/case_api                 |
+--------------------+------------------------------------------------+
| device_id          | User agent string from the request             |
+--------------------+------------------------------------------------+

Most errors are caught before the form is submitted, but some types of
issues may only be caught when the form is processed.  In these
instances, a XFormError is created, and no case changes will occur. The
server will return a 400 error response including the ID of the
XFormError and an error message.
