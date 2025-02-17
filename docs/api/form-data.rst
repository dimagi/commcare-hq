Form Data API
-------------

**Purpose:**
    Retrieve all data associated with a form submission, including all form property values. The form data may be presented to an end-user as detailed data associated with a particular case. For example, by clicking on a prenatal visit hyperlink in a case summary screen, the end user may be presented with clinical data associated with a specific prenatal visit.

**Authentication and Usage:**
    All URL endpoints should be used as part of a cURL authentication command. For more information, please review `API Authentication <https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2279637003/CommCare+API+Overview#API-Authentication>`_.

**Single Form URL:**

.. code-block:: text

    https://www.commcarehq.org/a/[domain]/api/[version]/form/[form_id]/

**Sample URL**

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
