Bulk Form Action
================

Overview
--------
**Purpose**
    Archive, unarchive, or delete a list of forms. The request
    returns immediately with a job id that can be polled for progress.

**Resource name:** ``bulk-action``

**Base URL**

.. code-block:: text

    https://www.commcarehq.org/a/[domain]/api/form/v1/bulk-action/

**Authentication:** API key only, sent in the ``Authorization`` header as
``ApiKey <username>:<api_key>``. Session and Basic authentication are not
accepted, and the key cannot be passed as a query parameter.

**Permissions Required:** the Edit Data and Access APIs permissions on the
user's role, and both the API Access and Data Cleanup privileges on the
project's plan.

Users whose role restricts them to specific locations cannot use this API.

Supported Endpoints and Methods
-------------------------------

=========================== =============================================
Endpoint                    Description
=========================== =============================================
POST /                      Start a bulk archive, unarchive, or delete job
GET /<id>/                  Get the status of a job
=========================== =============================================

Starting a Job
--------------

**Request**

.. code-block:: json

    {
      "action": "archive",
      "form_ids": ["3a1b...", "9c4d..."]
    }

``action``
    One of ``archive``, ``unarchive``, or ``delete``. See
    `Deleting Forms`_ for what deletion requires.

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
      "status_url": "https://www.commcarehq.org/a/[domain]/api/form/v1/bulk-action/0f3a9c..."
    }

Duplicate form ids are collapsed, so ``requested`` may be lower than the
number of ids submitted.

Jobs for a given project space run one at a time. If a job is submitted
while another is still running, it stays ``pending`` until the earlier one
finishes, and its ``processed`` count stays at 0 in the meantime. If a job
is unable to run for an extended period of time (hours), it is possible for
it to be marked ``failed``. If this happens, retry when there are no other
pending jobs.

Deleting Forms
--------------

.. warning::
    Deleting is permanent and cannot be undone. Archiving hides a form
    from reports and exports and can be reversed with ``unarchive``, so
    use that whenever data may be needed again.

A form must be archived before it can be deleted. Archiving is what
rebuilds the cases the form touched. Ids of forms that are not archived
are reported under the ``not_archived`` skip reason, and the rest of the
job still runs. To delete forms, archive them first and then submit
a second job for the delete.

Deleting a form that is already deleted counts as a success rather than a
skip, so a job can safely be retried.

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
      "action": "delete",
      "status": "complete",
      "requested_by": "user@example.com",
      "requested": 500,
      "processed": 500,
      "succeeded": 497,
      "skipped": {
        "not_found": ["ghi..."],
        "not_archived": ["jkl..."],
        "unexpected_error": ["mno..."]
      },
      "created_at": "2026-08-25T14:02:11.930000Z",
      "started_at": "2026-08-25T14:02:12.104000Z",
      "completed_at": "2026-08-25T14:03:40.882000Z"
    }

``status``
    One of ``pending``, ``running``, ``complete``, or ``failed``.
    ``complete`` means the job finished, not that every form succeeded.
    Compare ``succeeded`` against ``requested`` to understand success.

``skipped``
    Form ids that were not acted on, grouped by reason. Empty until the job
    reaches ``complete``. A job that ends as ``failed`` stopped before it
    could record them, so this stays empty.

    ==================== =================================================
    Reason               Meaning
    ==================== =================================================
    ``not_found``        No form with that id exists in this project space
    ``not_archived``     ``delete`` only: the form must be archived before
                         it can be deleted
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
403     The user lacks a required permission, the project's plan lacks
        a required privilege, or the user is restricted to specific
        locations
404     No such job in this project space
405     Method not allowed
429     Too many requests. Retry after the number of seconds given in the
        ``Retry-After`` header
======= ==================================================================

Error responses have the form ``{"error": "<message>"}``, except for 401,
which is plain text, and 429, which has an empty body.

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
