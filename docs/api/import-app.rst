Import Application API
======================

Overview
--------

**Purpose**
    Import an application from a JSON source file, and optionally upload
    multimedia assets for the imported application.

    This API provides three endpoints:

    1. **Import App** — Upload an application source JSON file to create
       a new application.
    2. **Upload Multimedia** — Upload a ZIP archive of multimedia files
       for an imported application (processed asynchronously).
    3. **Poll Multimedia Status** — Check the progress of an
       asynchronous multimedia upload.

**Authorization**
    API Key, Basic, Digest, or OAuth authentication. See
    `API Authentication <https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2279637003/CommCare+API+Overview#API-Authentication>`_.

**Permission Required**
    Edit Apps


Import App
----------

**Base URL**

.. code-block:: text

    https://www.commcarehq.org/a/[domain]/apps/api/import_app/

**Method**
    POST

**Body**
    Multipart Form Submission with File

Request & Response Details
~~~~~~~~~~~~~~~~~~~~~~~~~~

**Input Parameters**

.. list-table::
   :header-rows: 1

   * - Name
     - Description
     - Required
   * - app_file
     - The application source JSON file
     - yes
   * - app_name
     - Name for the imported application
     - yes

**Sample cURL Request**

.. code-block:: bash

    curl -X POST https://www.commcarehq.org/a/[domain]/apps/api/import_app/ \
         -u user@domain.com:password \
         -F "app_file=@app_source.json" \
         -F "app_name=My Imported App"

**Response (201 Created)**

.. code-block:: json

    {
      "success": true,
      "app_id": "abc123def456..."
    }

If the import succeeds but encounters non-fatal issues (e.g., missing
multimedia references or UCR configuration), the response includes a
``warnings`` field:

.. code-block:: json

    {
      "success": true,
      "app_id": "abc123def456...",
      "warnings": [
        "Copying the application succeeded, but the application is missing multimedia file(s)."
      ]
    }

**Error Responses**

.. list-table::
   :header-rows: 1

   * - Status
     - Condition
   * - 400
     - Missing ``app_file`` or ``app_name``, or the uploaded file is not
       valid JSON
   * - 403
     - Insufficient permissions
   * - 405
     - Request method is not POST


Upload Multimedia
-----------------

**Base URL**

.. code-block:: text

    https://www.commcarehq.org/a/[domain]/apps/api/[app_id]/multimedia/

**Method**
    POST

**Body**
    Multipart Form Submission with File

Request & Response Details
~~~~~~~~~~~~~~~~~~~~~~~~~~

**Input Parameters**

.. list-table::
   :header-rows: 1

   * - Name
     - Description
     - Required
   * - bulk_upload_file
     - A ZIP archive containing multimedia files (images, audio, video)
     - yes

**Sample cURL Request**

.. code-block:: bash

    curl -X POST https://www.commcarehq.org/a/[domain]/apps/api/[app_id]/multimedia/ \
         -u user@domain.com:password \
         -F "bulk_upload_file=@multimedia.zip"

**Response (200 OK)**

The multimedia upload is processed asynchronously. The response includes
a ``processing_id`` that can be used to poll for status.

.. code-block:: json

    {
      "success": true,
      "processing_id": "dl-abc123def456..."
    }

**Error Responses**

.. list-table::
   :header-rows: 1

   * - Status
     - Condition
   * - 400
     - Missing ``bulk_upload_file``, file is not a valid ZIP, or ZIP is
       corrupt
   * - 403
     - Insufficient permissions
   * - 404
     - Application not found in the specified domain
   * - 405
     - Request method is not POST


Poll Multimedia Status
-----------------------

**Base URL**

.. code-block:: text

    https://www.commcarehq.org/a/[domain]/apps/api/[app_id]/multimedia/status/[processing_id]/

**Method**
    GET

Request & Response Details
~~~~~~~~~~~~~~~~~~~~~~~~~~

**Sample cURL Request**

.. code-block:: bash

    curl https://www.commcarehq.org/a/[domain]/apps/api/[app_id]/multimedia/status/[processing_id]/ \
         -u user@domain.com:password

**Response (200 OK) — In Progress**

.. code-block:: json

    {
      "success": true,
      "complete": false,
      "in_celery": true,
      "progress": {
        "percent": 50,
        "current": 5,
        "total": 10
      },
      "errors": [],
      "processing_id": "dl-abc123def456..."
    }

**Response (200 OK) — Complete**

When processing is complete, the response includes details about matched
and unmatched files:

.. code-block:: json

    {
      "success": true,
      "complete": true,
      "in_celery": false,
      "progress": {
        "percent": 100,
        "current": 10,
        "total": 10
      },
      "errors": [],
      "processing_id": "dl-abc123def456...",
      "matched_count": 8,
      "unmatched_count": 2,
      "total_files": 10,
      "processed_files": 10,
      "image_count": 6,
      "audio_count": 2,
      "video_count": 0,
      "matched_files": {
        "CommCareImage": ["..."],
        "CommCareAudio": ["..."],
        "CommCareVideo": []
      },
      "unmatched_files": [
        {"path": "images/extra.png", "reason": "..."}
      ],
      "skipped_files": []
    }

**Error Responses**

.. list-table::
   :header-rows: 1

   * - Status
     - Condition
   * - 403
     - Insufficient permissions
   * - 404
     - Application not found, or processing ID not found / expired
   * - 500
     - The multimedia processing task failed
