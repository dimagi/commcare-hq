Case Data API
=============

Overview
--------

**Purpose**
    Retrieve all data associated with a case, including case property values, a list of associated forms, and referrals. The case data may be presented to the end user as a case details screen.

**Base URL**
.. code-block:: text

    https://www.commcarehq.org/a/[domain]/api/[version]/case/[case_id]/

**Authentication**
    For more information, please review `API Authentication <https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2279637003/CommCare+API+Overview#API-Authentication>`_.

Request & Response Details
---------------------------

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

.. list-table:: Case Metadata
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

.. list-table:: Special Case Properties
   :widths: 20 40 40
   :header-rows: 1

   * - Name
     - Description
     - Example
   * - owner_id
     - ID of the owner of the case (can be user or group)
     - -
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

.. list-table:: Start for Forms Associated with the Case. This repeats for each form, as seen in sample output below
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

    https://www.commcarehq.org/a/demo/api/v0.4/case/0X9OCW3JMV98EYOVN32SGN4II/?format=xml&properties=all&indices=all

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
        </properties>
        <indices>
            <case_ref1>
                <case_type>other_case_type</case_type>
                <case_id>8GPM05TVPIUH0Q4XLXVIURRTA</case_id>
            </case_ref1>
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
                </properties>
            </form>
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
        </referrals>
    </case>


Bulk Upload Case Data API
=========================

Overview
--------
**Purpose**
    Performs bulk imports of case data through the Excel Case Data Importer to either create or update cases.

**Base URL**

.. code-block:: text

    https://www.commcarehq.org/a/[domain]/importer/excel/bulk_upload_api/

**Method**
    POST

**Body**
    Multipart Form Submission with File

**Authorization**
    API Token or Basic Authorization

Request & Response Details
---------------------------

**Input Parameters**

.. list-table::
   :header-rows: 1

   * - Name
     - Description
     - Example
     - Required
     - Default (if optional)
   * - file
     - Path to the excel file containing Table Data
     - /home/username/household_case_upload.xlsx
     - yes
     - -
   * - case_type
     - The case type to be assigned to created cases
     - household
     - yes
     - -
   * - search_field
     - Whether to check for matches with existing cases against CommCareHQ's internal case id or an external named id
     - external_id
     - optional
     - case_id
   * - search_column
     - The column in the spreadsheet which will be matched against either the case_id or external_id
     - household_id
     - optional
     - case_id or external_id depending on search_field
   * - create_new_cases
     - Whether to create new cases when no existing case matches the search_field
     - on
     - optional
     - -
   * - name_column
     - The column in the spreadsheet which should be interpreted as the case name
     - household_name
     - optional
     - -

**Sample cURL Request**

.. code-block:: text

    curl -v https://www.commcarehq.org/a/[domain]/importer/excel/bulk_upload_api/ -u user@domain.com:password \
         -F "file=@household_case_upload.xlsx" \
         -F "case_type=household" \
         -F "search_field=external_id" \
         -F "search_column=household_id" \
         -F "create_new_cases=on"

(Note: Omitting the ':' and password will prompt curl to request it, preventing password exposure.)

**Note:**
    Uploads are subject to the same restrictions as the Excel Importer UI but with limited feedback. Testing uploads in the UI first is recommended.

**Response**

JSON output with the following parameters. A success code indicates processing but may include business-level errors.

.. list-table::
   :header-rows: 1

   * - Name
     - Description
     - Example
   * - code
     - 200: Success, 402: Warning, 500: Fail
     - 500
   * - message
     - Warning or Failure message
     - "Error processing your file. Submit a valid (.xlsx) file"
   * - status_url
     - URL to poll for processing status (State: 2 - Complete, 3 - Error)
     - https://www.commcarehq.org/a/demo/importer/excel/status/

- **Example JSON Response (Successful Upload):**

.. code-block:: json

    {
       "state": 2,
       "progress": {"percent": 0},
       "result": {
          "match_count": 0,
          "created_count": 15,
          "num_chunks": 0,
          "errors": []
       }
    }

- **Example JSON Response (Business Errors Encountered):**

.. code-block:: json

    {
       "state":2,
       "progress": {"percent":0},
       "result": {
          "match_count":0,
          "created_count":0,
          "num_chunks":0,
          "errors": [{
             "title":"Invalid Owner Name",
             "description":"Owner name was used in the mapping but there were errors when uploading because of these values.",
             "column":"owner_name",
             "rows": [2,3,4]
          }]
       }
    }
