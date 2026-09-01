Bulk Form Action
================

Overview
--------
**Purpose**
    Archive or unarchive a list of forms in the background. The request
    returns immediately with a job id that can be polled for progress.

.. note::
    This API is gated behind the ``bulk_form_actions_api`` feature flag and
    is not yet generally available.

**Resource name:** ``bulk-action``

**Base URL**

.. code-block:: text

    https://www.commcarehq.org/a/[domain]/api/form/v1/bulk-action/

**Authentication:** API key only, sent in the ``Authorization`` header as
``ApiKey <username>:<api_key>``. Session and Basic authentication are not
accepted, and the key cannot be passed as a query parameter.

**Permissions Required:** Edit Data and Access APIs. The project must also
have the Data Cleanup privilege.

Users whose role restricts them to specific locations cannot use this API.
They can continue to archive forms through the Manage Forms page.

Supported Endpoints and Methods
-------------------------------

=========================== ==========================================
Endpoint                    Description
=========================== ==========================================
POST /                      Start a bulk archive or unarchive job
GET /<id>/                  Get the status of a job
=========================== ==========================================

Starting a Job
--------------

**Request**

.. code-block:: json

    {
      "action": "archive",
      "form_ids": ["3a1b...", "9c4d..."]
    }

``action``
    Either ``archive`` or ``unarchive``.

``form_ids``
    A non-empty list of form ids, at most 5000 per request. Submit larger
    sets as multiple requests.

**Sample Output** (``202 Accepted``)

.. code-block:: json

    {
      "id": "0f3a9c...",
      "action": "archive",
      "status": "pending",
      "requested_by": "user@example.com",
      "requested": 500,
      "processed": 0,
      "succeeded": 0,
      "skipped": {},
      "created_at": "2026-08-25T14:02:11.930000Z",
      "started_at": null,
      "completed_at": null,
      "status_url": "https://www.commcarehq.org/a/[domain]/api/form/v1/bulk-action/0f3a9c.../"
    }

Duplicate form ids are collapsed, so ``requested`` may be lower than the
number of ids submitted.

Jobs for a given project space run one at a time. If a job is submitted
while another is still running, it stays ``pending`` until the earlier one
finishes, and its ``processed`` count stays at 0 in the meantime. A job
that waits more than about four hours for its turn is marked ``failed``.

Checking Job Status
-------------------

**Base URL**

.. code-block:: text

    https://www.commcarehq.org/a/[domain]/api/form/v1/bulk-action/[id]/

The response is the same object returned when the job was created, without
``status_url``.

.. code-block:: json

    {
      "id": "0f3a9c...",
      "action": "archive",
      "status": "complete",
      "requested_by": "user@example.com",
      "requested": 500,
      "processed": 500,
      "succeeded": 498,
      "skipped": {"not_found": ["ghi..."], "unexpected_error": ["jkl..."]},
      "created_at": "2026-08-25T14:02:11.930000Z",
      "started_at": "2026-08-25T14:02:12.104000Z",
      "completed_at": "2026-08-25T14:03:40.882000Z"
    }

``status``
    One of ``pending``, ``running``, ``complete``, or ``failed``.
    ``complete`` means the job finished, not that every form succeeded.
    Compare ``succeeded`` against ``requested``.

``skipped``
    Form ids that were not acted on, grouped by reason. Empty until the job
    reaches ``complete`` or ``failed``.

    ==================== =================================================
    Reason               Meaning
    ==================== =================================================
    ``not_found``        No form with that id exists in this project space
    ``unexpected_error`` The action failed for this form. The error is
                         logged for investigation
    ==================== =================================================

Errors
------

======= ==================================================================
Status  Cause
======= ==================================================================
400     Malformed JSON, a missing or unrecognized ``action``, or
        ``form_ids`` that is missing, empty, not a list of strings, or
        longer than 5000
401     Missing or invalid credentials
403     The user lacks a required permission, or is restricted to specific
        locations
404     No such job in this project space, or the feature flag is not
        enabled
405     Method not allowed
======= ==================================================================

Error responses have the form ``{"error": "<message>"}``.

Sample Usage
------------

.. code-block:: bash

    curl -X POST \
      https://www.commcarehq.org/a/[domain]/api/form/v1/bulk-action/ \
      -H "Authorization: ApiKey user@example.com:[api_key]" \
      -H "Content-Type: application/json" \
      -d '{"action": "archive", "form_ids": ["3a1b...", "9c4d..."]}'

.. code-block:: bash

    curl https://www.commcarehq.org/a/[domain]/api/form/v1/bulk-action/[id]/ \
      -H "Authorization: ApiKey user@example.com:[api_key]"
