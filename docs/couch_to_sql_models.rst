.. _couch-to-sql-model-migration:

***************************************
Migrating models from couch to postgres
***************************************

This is a step by step guide to migrating a single model from couch to postgres.

Selecting a Model
################

To find all classes that descend from `Document`:
::

    from dimagi.ext.couchdbkit import Document

    def all_subclasses(cls):
        return set(cls.__subclasses__()).union([s for c in cls.__subclasses__() for s in all_subclasses(c)])

    sorted([str(s) for s in all_subclasses(Document)])

To find how many documents of a given type exist in a given environment:
::

    from corehq.dbaccessors.couchapps.all_docs import get_doc_ids_by_class, get_deleted_doc_ids_by_class
    
    len(list(get_doc_ids_by_class(MyDocumentClass) + get_deleted_doc_ids_by_class(MyDocumentClass)))

There's a little extra value to migrating models that have dedicated views:
::

    grep -r MyDocumentClass . | grep _design.*map.js

There's a lot of extra value in migrating areas where you're familiar with the code context.

Ultimately, all progress is good.

Conceptual Steps
################

1. Add SQL model
2. Wherever the couch document is saved, create or update the corresponding SQL model
3. Migrate all existing couch documents
4. Whenever a couch document is read, read from SQL instead
5. Delete couch model and any related views

Practical Steps
###############

Even a simple model takes several pull requests to migrate, to avoid data loss while deploys and migrations are in progress. Best practice is a minimum of three pull requests, described below, each deployed to all large environments before merging the next one.

See `SyncCouchToSQLMixin <https://github.com/dimagi/commcare-hq/blob/c2b93b627c830f3db7365172e9be2de0019c6421/corehq/ex-submodules/dimagi/utils/couch/migration.py#L4>`_ and `SyncSQLToCouchMixin <https://github.com/dimagi/commcare-hq/blob/c2b93b627c830f3db7365172e9be2de0019c6421/corehq/ex-submodules/dimagi/utils/couch/migration.py#L115>`_ for possibly helpful code.

PR 1: Add SQL model and migration management command, write to SQL
****
This should contain:

* A new model
* A django migration to create the new model
* A standalone management command that fetches all couch docs and creates a corresponding SQL model if it doesn't already exist. This command should support being run repeatedly.
* Updates to all code that saves the couch document to also update the SQL model (and creeate it if necessary). If it isn't feasible to update all couch-saving code in this PR, the migration command will need to not only create new SQL models but also update existing models if they've deviated from their couch document.

Once this PR is deployed, run the migration command in any environments where it's likely to take more than a trivial amoount of time.

`Sample PR 1 <https://github.com/dimagi/commcare-hq/pull/26025>`_ - note that this PR does not split the migration out as a management command but instead

PR 2: Verify migration and read from SQL
****
This should contain:

* A django migration that verifies all couch docs have been migrated and cleans up any stragglers, using the `auto-managed migration pattern <https://commcare-hq.readthedocs.io/migration_command_pattern.html#auto-managed-migration-pattern>`_
* Replacements of all code that reads from the couch document to instead read from SQL.

For models with many references, it may make sense to do this work incrementally, with a first PR that includes the verification migration and then subsequent PRs that update a subset of reads.

`Sample PR 2 <https://github.com/dimagi/commcare-hq/pull/26026>`_

PR 3: 
****
This is the cleanup PR. Wait a few days or weeks after the previous PR to merge this one; there's no rush. Clean up:

* Remove the old couch model
* Add the couch class to `deletable_doc_types <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/cleanup/deletable_doc_types.py>`_
* Remove any couch views that are no longer used. Remember this may require a reindex; see the `main db migration docs <https://commcare-hq.readthedocs.io/migrations.html>`_

`Sample PR 3 <https://github.com/dimagi/commcare-hq/pull/26027>`_
