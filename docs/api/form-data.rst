Form Data API
=============

Overview
--------

Fetch all data associated with a form submission, or list form
submissions. These operations, along with the list endpoint, are
documented together in :doc:`list-forms`.

Form Attachments
-----------------

Overview
--------

**Purpose**
    Retrieve an attachment associated with a form submission. These attachments can include images, audio files, or any other supported file type collected through a form submission.

**Base URL:**

.. code-block:: text

    https://www.commcarehq.org/a/[domain]/api/form/attachment/{form_id}/{attachment_name}

**Authentication**
    All URL endpoints should be used as part of a cURL authentication command. For more information, please review `API Authentication <https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2279637003/CommCare+API+Overview#API-Authentication>`_.

**Permission Required**
    Edit Data

Request & Response Details
---------------------------

**Sample URL**

.. code-block:: text

    https://www.commcarehq.org/a/corpora/api/form/attachment/2150db25-a1e0-496c-9340-c232be866ec6/waytogo.mp3

**Response**

The API returns a **200 OK** response upon a successful request and provides the requested attachment in its original format.
