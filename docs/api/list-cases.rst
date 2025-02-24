List Cases (Version 3+)
=======================

Overview
--------

**Purpose**
    Retrieves a list of cases. The list of cases may be presented to the end user as a simple list of cases, where each case name incudes a hyperlink to access detailed information about the case.

**Base URL**

.. code-block:: text

    https://www.commcarehq.org/a/[domain]/api/v0.5/case/

**Authentication**
    For more information, please review `this <https://dimagi.atlassian.net/wiki/x/LwXKfw>`_.

Request & Response Details
---------------------------

**Input Parameters**

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


**Output Values**

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

**Sample Usage**

.. code-block:: text

    https://www.commcarehq.org/a/[domain]/api/v0.5/case/?format=xml

**Sample XML Output**

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
        ...
    </cases>

**Sample JSON Output**

.. code-block:: json

    [
      {
        "case_id": "45WKYXQRFFU3AT4Y022EX7HF2",
        "closed": false,
        "date_closed": null,
        "date_modified": "2012-03-13T18:21:52Z",
        "domain": "demo",
        "indices": {},
        "properties": {
          "case_name": "ryan",
          "case_type": "programmer",
          "date_opened": "2012-03-13T18:21:52Z",
          "external_id": "45WKYXQRFFU3AT4Y022EX7HF2",
          "gender": "m",
          "languages": "python java javascript c php erlang love",
          "owner_id": null,
          "role": "artisan"
        },
        "server_date_modified": "2012-04-05T23:56:41Z",
        "server_date_opened": "2012-04-05T23:56:41Z",
        "user_id": "06414101dc45bcfdc963b8cb1a1ebdfd",
        "version": "1.0",
        "xform_ids": [ "3HQEXR2S0GIRFY2GF40HAR7ZE" ]
      },
      ...
    ]
