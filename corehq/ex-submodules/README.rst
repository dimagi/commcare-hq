Ex-Submodules in CommCare HQ
############################

This area contains sections of code that used to be their own repositories but have since been folded back into the
``commcare-hq`` codebase. For those that do not have READMEs, documentation typically still exists in the archived
repository.

A lot of this is couch-related and therefore on its way out as we move more functionality to postgres, but a few of
these are actively used, especially casexml, pillowtop, soil, and toggle.

All of the pillow-y names were created as riffs on the "couch" in CouchDB.

casexml
    An application for working with `CaseXML <https://github.com/dimagi/commcare-core/wiki/casexml20>`_.
couchexport
    Tooling to export couch documents to other formats, particularly Excel. Used by areas of HQ that involve
    downloading couch-based models in bulk.
couchforms
    Puts XForms in CouchDB. Effectively deprecated, as the vast majority of forms have been migrated from couch to
    postgres.
dimagi
    Miscellaneous utilities.
phonelog
    This manages device logs, which are reports of mobile device activity that can be sent to HQ for analysis.
pillow_retry
    Related to ``pillow_top``, This manages a queue for retrying pillow errors.
pillowtop
    A framework for listening to changes, then transforming and processing them.
    Originally modeled after CouchDB's ``_changes`` feed.
soil
    An application to schedule long-running tasks and later retrieve their results. This is used for
    many of HQ's long-running tasks that result in a file download.
toggle
    A CouchDB-backed app for feature flags that control access to functionality on a user-specific or domain-specific basis.
