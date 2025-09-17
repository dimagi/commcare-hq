Bulk Upload Case Data API
=========================

Overview
--------
**Purpose**
    Performs bulk imports of case data through the `Excel Case Data Importer <https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2143946828/Case+Import+with+Excel>`_ to either create or update cases.

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
     -
   * - case_type
     - The case type to be assigned to created cases
     - household
     - yes
     -
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
     -
   * - name_column
     - The column in the spreadsheet which should be interpreted as the case name
     - household_name
     - optional
     -


**Sample cURL Request**

.. code-block:: text

    curl -v https://www.commcarehq.org/a/[domain]/importer/excel/bulk_upload_api/ -u user@domain.com:password \
         -F "file=@household_case_upload.xlsx" \
         -F "case_type=household" \
         -F "search_field=external_id" \
         -F "search_column=household_id" \
         -F "create_new_cases=on"

(You may also omit the ':' and password and curl will request it. This will have the benefit of not showing your password on your screen or storing it in your history.)

.. note::

    Uploads are subject to the same restrictions as the Excel Importer User Interface, but with much more limited feedback. It is a good idea to test uploads there first to debug any issues, then use the Bulk Upload API to automate future imports once they are working as expected.

**Response**

JSON output with following Parameters. Note that a success code indicates that the upload was processed, but it may have encountered business-level problems with the import's data, such as uploading a case to an invalid location. Also note that these parameters may change to support for better error handling, so do not plan around them.

.. list-table::
   :header-rows: 1

   * - Name
     - Description
     - Example
   * - code
     - 200: Success, 402: Warning, 500: Fail
     - ``500``
   * - message
     - Warning or Failure message
     - "Error processing your file. Submit a valid (.xlsx) file"
   * - status_url
     - If an upload is successful, a URL to poll for the status of the processing (State: 2 - Complete, 3 - Error)
     - ::

         JSON result from hitting status url:
         {
            "state": 2,
            "progress": {"percent": 0},
            "result": {
               "match_count": 0,
               "created_count": 15
               "num_chunks": 0,
               "errors": []
            }
         }

         JSON result where upload succeeded but encountered business errors:
         {
            "state": 2,
            "progress": {"percent": 0},
            "result": {
               "match_count": 0,
               "created_count": 0,
               "num_chunks": 0,
               "errors": [{
                  "title": "Invalid Owner Name",
                  "description": "Owner name was used in the mapping but there were errors when uploading because of these values.",
                  "column": "owner_name",
                  "rows": [2, 3, 4]
               }]
            }
         }
