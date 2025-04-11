Case Data API v1
================

List Cases
----------

**Purpose**
    Retrieves a list of cases. The list of cases may be presented to the end user as a simple list of cases, where each case name incudes a hyperlink to access detailed information about the case.

**Base URL**

.. code-block:: text

    https://www.commcarehq.org/a/[domain]/api/case/v1/

**Authentication**
    For more information, please review `API Authentication <https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2279637003/CommCare+API+Overview#API-Authentication>`_.

**Permission Required**
    Edit Data

Request & Response Details
..........................

**Input Parameters**

In addition to all `Case Data API <case-data.rst>`_ parameters, you may use the following input parameters to filter results and control paging:

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

    https://www.commcarehq.org/a/[domain]/api/case/v1/?format=xml

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
      "..."
    ]


Case Data Details
-----------------

**Purpose**
    Retrieve all data associated with a case, including case property values, a list of associated forms, and referrals. The case data may be presented to the end user as a case details screen.

**Base URL**

.. code-block:: text

    https://www.commcarehq.org/a/[domain]/api/case/v1/[case_id]/

**Authentication**
    For more information, please review `API Authentication <https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2279637003/CommCare+API+Overview#API-Authentication>`_.

**Permission Required**
    Edit Data

Request & Response Details
..........................

**Input Parameters**

.. list-table::
   :widths: 20 40 15 25 20
   :header-rows: 1

   * - Name
     - Description
     - Values
     - Example
     - Status
   * - format
     - Return data format
     - xml, json
     - format=xml
     - Supported
   * - properties
     - Whether to include properties
     - all, none
     - properties=all
     - Proposed
   * - indices
     - Whether to include indices
     - all, none
     - indices=all
     - Proposed
   * - xforms_by_name__full
     - Whether to include all xforms by name
     - true
     - xforms_by_name__full=true
     - Supported
   * - xforms_by_xmlns__full
     - Whether to include all xforms by xmlns
     - true
     - xforms_by_xmlns__full=true
     - Supported
   * - child_cases__full
     - Whether to include child cases
     - true
     - child_cases__full=true
     - Supported since version 4
   * - parent_cases__full
     - Whether to include parent cases
     - true
     - parent_cases__full=true
     - Supported since version 4

**Output Values**

.. list-table:: *Case Metadata*
   :widths: 20 40 40
   :header-rows: 1

   * - Name
     - Description
     - Example
   * - case_id
     - Case UUID
     - 0X9OCW3JMV98EYOVN32SGN4II
   * - user_name
     - User name of case owner, including domain
     - jdoe@example.commcarehq.org
   * - user_id
     - UUID of user that owns the case
     - 3c5a623af057e23a32ae4000cf291339
   * - date_modified
     - Date and time case was last modified
     - 2011-12-13T15:09:47Z
   * - closed
     - Status of the case (open, closed)
     - false
   * - date_closed
     - Date and time case was closed
     - 2011-12-20T15:09:47Z
   * - properties
     - List of all editable case properties, including both special predefined properties and user-defined dynamic properties
     -

.. list-table:: *Special Case Properties*
   :widths: 20 40 40
   :header-rows: 1

   * - Name
     - Description
     - Example
   * - owner_id
     - ID of the owner of the case (can be user or group)
     -
   * - case_name
     - Name of case
     - Rose
   * - external_id
     - External ID associated with the case
     - 123456
   * - case_type
     - Type of case
     - pregnancy
   * - date_opened
     - Date and time case was opened
     - 2011-11-16T14:26:15Z
   * - indices
     - End of special properties with a list of references to other cases with properties <case_type/> and <case_id/>
     -

.. list-table:: *Start for Forms Associated with the Case. This repeats for each form, as seen in sample output below*
   :widths: 20 40 40
   :header-rows: 1

   * - Name
     - Description
     - Example
   * - form_id
     - UUID of form associated with the case
     - 1J9NF7B4FTH73435PYJJSL5SJ
   * - form_name
     - Name of form associated with the case
     - Prenatal visit
   * - started_on
     - Date and time form was started
     - 2011-11-16T14:26:15Z
   * - ended_on
     - Date and time form was completed
     - 2011-11-16T14:27:35Z


**Sample Usage**

.. code-block:: text

    https://www.commcarehq.org/a/demo/api/case/v1/0X9OCW3JMV98EYOVN32SGN4II/?format=xml&properties=all&indices=all

**Sample Output**

.. code-block:: xml

    <case>
        <domain>example</domain>
        <case_id>0X9OCW3JMV98EYOVN32SGN4II</case_id>
        <username>jdoe@example.commcarehq.org</username>
        <user_id>3c5a623af057e23a32ae4000cf291339</user_id>
        <closed>false</closed>
        <date_closed>2011-12-20 15:09:47Z</date_closed>
        <date_modified>2011-12-13 15:09:47Z</date_modified>
        <properties>
            <case_name>Rose</case_name>
            <case_type>pregnancy</case_type>
            <date_opened>2011-11-16T14:26:15Z</date_opened>
            <external_id>123456</external_id>
            <owner_id>3c5a623af057e23a32ae4000cf291339</owner_id>
            <case_property1>Dynamic property value 1</case_property1>
            <case_property2>Dynamic property value 2</case_property2>
            ...
        </properties>
        <indices>
            <case_ref1>
                <case_type>other_case_type</case_type>
                <case_id>8GPM05TVPIUH0Q4XLXVIURRTA</case_id>
            </case_ref1>
            ...
        </indices>
        <forms>
            <form>
                <form_id>1J9NF7B4FTH73435PYJJSL5SJ</form_id>
                <form_name>Prenatal visit</form_name>
                <started_on>2011-11-16T14:26:15Z</started_on>
                <ended_on>2011-11-16T14:27:35Z</ended_on>
                <properties>
                    <form_property1>Dynamic property value 1</form_property1>
                    <form_property2>Dynamic property value 2</form_property2>
                    ...
                </properties>
            </form>
            ...
        </forms>
        <referrals>
            <referral>
                <referral_id>D8LZS28LEUWU7W9QNDM89XWPL</referral_id>
                <referral_type>referred_to_health_center</referral_type>
                <opened_on>2011-11-17T14:26:15Z</opened_on>
                <modified_on>2011-11-17T14:27:10Z</modified_on>
                <followup_on>2011-11-19T00:00:00Z</followup_on>
                <referral_status>open</referral_status>
            </referral>
            ...
        </referrals>
        ...
    </case>
