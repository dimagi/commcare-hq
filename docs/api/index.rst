=============
CommCare APIs
=============

CommCare APIs provide access to various system functionalities, including data retrieval, case and form submissions, and user management. This page describes different APIs available for integration.

Table of contents
-----------------

Data APIs
~~~~~~~~~

These APIs are intended for building project-specific applications and integrations, including:

- Custom end-user applications that address project-specific needs.
- Custom integrations with external back-end systems, such as an electronic patient record system.

In the following, ``[version]`` should always be replaced with one of ``v0.4``, ``v0.3``, etc. These documents only describe the latest version—prior versions remain available only to support backwards compatibility with deployed systems, not for general use. The latest version is ``v0.5``.

You can browse and test the Data APIs using the `CommCare API Explorer <https://commcare-api-explorer.dimagi.com/>`_.

**Implementation of URL Endpoints** - All URL endpoints should be utilized as part of a cURL authentication command. For more information, please review CommCare's API Authentication Documentation: `API Authentication <https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2279637003/CommCare+API+Overview#API-Authentication>`_.

.. toctree::
    :maxdepth: 1

    application-structure
    form-data
    case-data
    list-cases
    list-forms
    list-groups
    list-mobile-workers
    list-webusers
    bulk-user
    list-reports
    locations
    fixture
    ota-api-restore
    form-case-forwarding
    download-report-data

User APIs
~~~~~~~~~
The User APIs provide endpoints for managing mobile and web users, including creation, editing, deletion, and authentication. These APIs also support group management, Single Sign-On, and user identity verification.

.. toctree::
    :maxdepth: 1

    mobile-worker
    user-domain-list
    user-group
    webuser
    sso

Form Submission API
~~~~~~~~~~~~~~~~~~~
CommCare's Submission API implements the OpenRosa standard Form Submission API for submitting XForms over HTTP/S.

.. toctree::
    :maxdepth: 1

    form-submission

SMS APIs
~~~~~~~~
SMS APIs enable sending and receiving SMS messages through CommCare, allowing integration with external systems for automated messaging, notifications, and data collection. These APIs support message scheduling, two-way communication, and customization based on workflow needs.

.. toctree::
    :maxdepth: 1

    messaging-events
    sms-user-registration
    send-install-info-sms
