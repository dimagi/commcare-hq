List Forms
==========

Overview
--------

**Purpose**
    Get a list of form submissions.

**Base URL**

.. code-block:: text

    https://www.commcarehq.org/a/[domain]/api/v0.5/form/

**Authentication**
    For more information, please review `API Authentication <https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2279637003/CommCare+API+Overview#API-Authentication>`_.

**Permission Required**
    Edit Data

Request & Response Details
---------------------------

**Input Parameters**

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

**Sample Usage**

.. code-block:: text

    https://www.commcarehq.org/a/[domain]/api/v0.5/form/

**Sample JSON Output**

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
          "attachments": {
            "form.xml": {
              "content_type": "text/xml",
              "length": 1103
            }
          },
          "build_id": "e0a6125",
          "domain": "my-project",
          "form": {
            "#type": "data",
            "@name": "Case Update",
            "@uiVersion": "1",
            "@version": "18",
            "@xmlns": "http://openrosa.org/formdesigner/4281EB62-46E6-49AD-A08C",
            "case": {
              "@case_id": "b6996b7b-6b3f-476a-9006",
              "@date_modified": "2016-11-29T14:50:41.156000Z",
              "@user_id": "e7ad965c",
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
            "data_node": "55",
            "geodata": "5.0 5.0 5.0 5.0",
            "meta": {
              "@xmlns": "http://openrosa.org/jr/xforms",
              "appVersion": "CommCare Android, version \"2.31.0\"(423345). App v18. CommCare Version 2.31. Build 423345, built on: 2016-11-02",
              "app_build_version": 18,
              "commcare_version": "2.31.0",
              "deviceID": "358001070684648",
              "geo_point": null,
              "instanceID": "f959449c-8776-42ac-b776-3f564fafc331",
              "timeEnd": "2016-11-29T14:50:41.156000Z",
              "timeStart": "2016-11-29T14:50:36.155000Z",
              "userID": "e7ad965c70802884a7a67add763939e8",
              "username": "testuser"
            },
            "old_data_node": "",
            "question1": "OK",
            "question11": "5",
            "question12": "2012-09-26",
            "question14": "OK",
            "question3": "b",
            "question7": "b",
            "text": "TEST"
          },
          "id": "f959449c-8776-42ac-b776-3f564fafc331",
          "initial_processing_complete": true,
          "is_phone_submission": "2.0",
          "metadata": {
            "appVersion": "CommCare Android, version \"2.31.0\"(423345). App v18. CommCare Version 2.31. Build 423345, built on: 2016-11-02",
            "app_build_version": 18,
            "commcare_version": "2.31.0",
            "deprecatedID": null,
            "deviceID": "358001070684648",
            "doc_type": "Metadata",
            "geo_point": null,
            "instanceID": "f959449c-8776-42ac-b776-3f564fafc331",
            "location": null,
            "timeEnd": "2016-11-29T14:50:41.156000",
            "timeStart": "2016-11-29T14:50:36.155000",
            "userID": "e7ad965c70802884a7a67add763939e8",
            "username": "simon"
          },
          "problem": null,
          "received_on": "2016-11-29T14:50:42.530616Z",
          "resource_uri": "",
          "server_modified_on": "2016-11-29T14:50:42.530616Z",
          "type": "data",
          "uiversion": "1",
          "version": "18"
        }
      ]
    }

