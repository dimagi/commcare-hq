.. This is the main index for HQ's docs.

Welcome to CommCare HQ's documentation!
=======================================

CommCare is a multi-tier mobile, server, and messaging platform. The platform enables users to build and
configure content and a user interface, deploy that application to Android devices or to an end-user-facing web
interface for data entry, and receive that data back in real time. In addition, content may be defined that
leverages bi-directional messaging to end-users via API interfaces to SMS gateways, e-mail systems, or other
messaging services. The system uses multiple persistence mechanisms, analytical frameworks, and open source
libraries.

Data on CommCare mobile is stored encrypted-at-rest (symmetric AES256) by keys that are secured by the
mobile user’s password. User data is never written to disk unencrypted, and the keys are only ever held in memory,
so if a device is turned off or logged out the data is locally irretrievable without the user’s password.
Data is transmitted from the phone to the server (and vis-a-versa) over a secure and encrypted HTTPS channel.

**Contents:**

..
    list rst documents here, and it'll be added to the index,
    including any subsections inside those docs (up to the maxdepth).
    For reference on generating a toc, check out the sphinx docs on
    the subject: http://sphinx-doc.org/markup/toctree.html
    Here's a sample well-organized toc:
    https://github.com/kennethreitz/python-guide/blob/master/docs/contents.rst.inc

.. toctree::
    :caption: Overview
    :maxdepth: 1

    overview/platform
    overview/architecture
    cep

.. toctree::
    :caption: Application Building
    :maxdepth: 1

    apps/terminology
    apps/translations
    apps/multimedia
    apps/settings
    apps/advanced_app_features
    apps/suite_generation
    apps/builds
    web_apps
    formplayer
    case_search_query_language

.. toctree::
    :caption: Application Data Layer
    :maxdepth: 1

    restore-logic

.. toctree::
    :caption: Tenant Management
    :maxdepth: 1

    locations

.. toctree::
    :caption: Analytics
    :maxdepth: 1

    reporting
    exports
    change_feeds
    pillows
    email_monitoring_SES

.. toctree::
    :caption: User-Configurable Reporting
    :maxdepth: 1

    ucr
    ucr/examples
    ucr/faq
    ucr/mobile_ucr_v2_migration_guide

.. toctree::
    :caption: Messaging
    :maxdepth: 1

    messaging/index

.. toctree::
    :caption: Integrations
    :maxdepth: 1

    api
    fhir/index
    openmrs
    value_source

.. toctree::
    :caption: Single Sign On (SSO)
    :maxdepth: 1

    sso/overview
    sso/architecture
    sso/local_setup
    sso/adding_idp

.. toctree::
    :caption: UI and Front End
    :maxdepth: 1

    translations
    ui_helpers
    class_views
    forms
    js-guide/README

.. toctree::
    :caption: Testing
    :maxdepth: 1

    testing
    test_coverage
    mocha
    es_fake

.. toctree::
    :caption: Performance
    :maxdepth: 1

    profiling
    caching_and_memoization

.. toctree::
    :caption: Code
    :maxdepth: 1

    toggles/index
    commtrack
    elasticsearch
    middleware
    nfs
    forms_and_cases
    couchdb
    celery
    databases
    metrics
    extensions
    custom

.. toctree::
    :caption: Migrations
    :maxdepth: 1

    migrations_in_practice
    migration_command_pattern
    migrations
    couch_to_sql_models

.. toctree::
    :caption: Architecture Decisions
    :maxdepth: 1
    :glob:

    decisions/*

.. toctree::
    :caption: Documentation Tips

    documenting

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

