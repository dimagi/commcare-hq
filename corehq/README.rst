corehq
############################

A few broad areas of functionality are stored directly in this directory.

apps
    Most functionality lives in this directory. See README in this directory for details.
blobs
    The blob db stores large pieces of binary data. It's where form XML, multimedia, exports, temporary files, etc. are stored.
celery_monitoring
    Tools to monitor `Celery <https://docs.celeryproject.org/en/stable/>`_, which we use for async task processing.
couchapps
    Certain couch views are stored here, instead of inside the relevant django app, because storing them separately
    gives us performance benefits.
dbaccessors
    Part of ``couchapps``
ex-submodules
    Assorted functionality that used to live in separate repositories. See README in this directory for details.
extensions
    Framework for extending HQ functionality in a fork-like way. Used to handle code specific to ICDS-CAS.
form_processor
    Code to handle receiving, processing, and storing form submissions from CommCare mobile and Web Apps.
messaging
    Code to manage direct-to-user messages in CommCare HQ, most often SMS but also channels like email and
    whatsapp. Also see the ``sms`` and ``smsforms`` apps in ``corehq.apps``.
motech
    MOTECH is CommCare HQ's integration layer, and allows HQ to forward data to
    remote systems' APIs, to import data from them, and to follow workflows for
    more complex integrations with systems like OpenMRS and DHIS2.
pillows
    HQ-specific mappings that use the ``pillowtop`` framework in ``ex-submodules``.
preindex
    Code for handling preindexing, which updates CouchDB views and ElasticSearch indices.
    Preindex is run as part of deploy and can also be run ad hoc.
privileges.py
    Privileges allow HQ to limit functionality based on software plan.
project_limits
    Framework for throttling actions like form submissions on a domain-specific basis.
sql_accessors
    Stores custom postgres functions.
sql_db
    Code related to partitioning postgres.
sql_proxy_accessors
    Stores custom postgres functions that use `PL/Proxy <https://plproxy.github.io/>`_.
sql_proxy_standby_accessors
    Stores custom postgres functions relevant to standby servers.
tabs
    Menu structure for CommCare HQ.
tests
    Contains a few tests for high-level functionality like locks, as well as tooling to run tests with
    `pytest <https://docs.pytest.org/en/stable/>`_.
toggles.py
    Toggles allow limiting functionality based on user or domain. Also see ``ex-submodules/toggle`` and ``corehq.apps.toggle_ui``.
util
    Miscellaneous utilities. Also see ``ex-submodules/dimagi``.
