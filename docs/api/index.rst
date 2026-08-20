=============
CommCare APIs
=============

CommCare APIs provide access to various system functionalities,
including data retrieval, case and form submissions, and user
management. This page describes different APIs available for
integration.

Using the CommCare APIs
------------------------

The CommCare APIs require a Software Plan of Standard or higher.

Authentication
~~~~~~~~~~~~~~

Requests authenticate with an API key, HTTP Basic, HTTP Digest, or OAuth2.
API key authentication sends the key in an ``Authorization`` header::

    Authorization: ApiKey <username>:<api-key>

For a web user the username is the email address the account signs in
with. Generate a key from your account settings under *API Keys*. A key
can be scoped to a single project space and to a set of IP addresses.

URL structure
~~~~~~~~~~~~~

Most endpoints are scoped to a project space::

    https://www.commcarehq.org/a/<domain>/api/<resource>/<version>/

A few are scoped to the authenticated user rather than a project space, and
omit the domain::

    https://www.commcarehq.org/api/<resource>/<version>/

Versioning
~~~~~~~~~~

The version in the URL changes only for a breaking change. Adding a field to
a response, or a new optional parameter, does not bump the version — so a
client must tolerate unfamiliar fields.

Pagination
~~~~~~~~~~

List endpoints accept ``limit`` and ``offset`` and return a ``meta`` object
with ``limit``, ``offset``, ``total_count``, ``next`` and ``previous``.
Follow ``next`` until it is ``null`` rather than computing offsets, and note
that some endpoints paginate by cursor instead.

Rate limiting
~~~~~~~~~~~~~

Requests are throttled per project space. A throttled request is answered
with a ``Retry-After`` header giving the seconds to wait.

The API reference
~~~~~~~~~~~~~~~~~

Every documented API has a reference page listing its endpoints, parameters
and response fields, generated from the API's OpenAPI specification:

- `API reference index <https://www.commcarehq.org/api/docs/>`_
- `Machine-readable OpenAPI document <https://www.commcarehq.org/api/openapi.json>`_

That document covers every documented endpoint in one OpenAPI 3.0.3 file, and
is the one to point a code generator or an agent at. Each API's own
specification is served from its reference page.

The pages below give a sentence of orientation per API and link to its
reference.

Table of contents
-----------------

Data APIs
~~~~~~~~~

These APIs are intended for building project-specific applications and
integrations, including:

- Custom end-user applications that address project-specific needs.

- Custom integrations with external back-end systems, such as an
  electronic patient record system.

You can browse and test the Data APIs using the
`CommCare API Explorer <https://commcare-api-explorer.dimagi.com/>`_.

**Implementation of URL Endpoints** - All URL endpoints should be
utilized as part of a cURL authentication command. For more information,
please review CommCare's API Authentication Documentation:
`API Authentication <https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2279637003/CommCare+API+Overview#API-Authentication>`_.

.. toctree::
    :maxdepth: 1

    application-structure
    import-app
    form-data
    cases-v1
    cases-v2
    bulk-upload-cases
    list-forms
    list-groups
    list-mobile-workers
    list-webusers
    bulk-user
    list-reports
    download-report-data
    locations-v1
    locations-v2
    location-types
    fixture
    ota-api-restore
    det-exports


User APIs
~~~~~~~~~

The User APIs provide endpoints for managing mobile and web users,
including creation, editing, deletion, and authentication. These APIs
also support group management, Single Sign-On, and user identity
verification.

.. toctree::
    :maxdepth: 1

    mobile-worker
    user-domain-list
    user-group
    webuser
    sso

Form Submission API
~~~~~~~~~~~~~~~~~~~

CommCare's Submission API implements the OpenRosa standard Form
Submission API for submitting XForms over HTTP/S.

.. toctree::
    :maxdepth: 1

    form-submission

SMS APIs
~~~~~~~~

SMS APIs enable sending and receiving SMS messages through CommCare,
allowing integration with external systems for automated messaging,
notifications, and data collection. These APIs support message
scheduling, two-way communication, and customization based on workflow
needs.

.. toctree::
    :maxdepth: 1

    messaging-events
