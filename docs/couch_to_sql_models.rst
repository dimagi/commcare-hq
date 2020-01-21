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

A note on source control: it's best to create all pull requests at once so that reviewers have full context on the migration. It's easier to do the work in a single branch and then make the branches for individual PRs later on. If you don't typically run a linter before PRing, let the linter run on each PR and fix errors before opening the next one.

See `SyncCouchToSQLMixin <https://github.com/dimagi/commcare-hq/blob/c2b93b627c830f3db7365172e9be2de0019c6421/corehq/ex-submodules/dimagi/utils/couch/migration.py#L4>`_ and `SyncSQLToCouchMixin <https://github.com/dimagi/commcare-hq/blob/c2b93b627c830f3db7365172e9be2de0019c6421/corehq/ex-submodules/dimagi/utils/couch/migration.py#L115>`_ for possibly helpful code.

PR 1: Add SQL model and migration management command, write to SQL
****
This should contain:

* A new model, with a django migration to create it. `Sample commit for Dhis2Connection <https://github.com/dimagi/commcare-hq/pull/26398/commits/9acba210c8b780b2ba13b58e684a2b5ccc52f13e>`_, a simple class with no methods.
* A standalone management command that fetches all couch docs and creates a corresponding SQL model if it doesn't already exist. Use the base class `PopulateSQLCommand <https://github.com/dimagi/commcare-hq/blob/9a953daffe54e01563caf6106a9411378a07ab1a/corehq/apps/cleanup/management/commands/populate_sql_model_from_couch_model.py>`_. `Sample commit for Dhis2Connection <https://github.com/dimagi/commcare-hq/blob/9a953daffe54e01563caf6106a9411378a07ab1a/corehq/apps/app_manager/management/commands/populate_sql_global_app_config.py>`_.
* Updates to all code that saves the couch document to also update the SQL model (and create it if necessary). If it isn't feasible to update all couch-saving code in this PR, the migration command will need to not only create new SQL models but also update existing models if they've deviated from their couch document. `Sample commit for Dhis2Connection <https://github.com/dimagi/commcare-hq/pull/26398/commits/b38461f63d8b4c4a13e2dc43d3808c99c5cdb292>`_.
* Code to delete the new model when the domain is deleted. Add the new model to `DOMAIN_DELETE_OPERATIONS <https://github.com/dimagi/commcare-hq/blob/522294560cee0f3ac1ddeae0501d653b1ea0f215/corehq/apps/domain/deletion.py#L179>`_ and update tests in `test_delete_domain.py <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/domain/tests/test_delete_domain.py>`_. `Sample PR that handles several app manager models <https://github.com/dimagi/commcare-hq/pull/26310/files>`_.

Once this PR is deployed, run the migration command in any environments where it's likely to take more than a trivial amoount of time.

PR 2: Verify migration and read from SQL
****
This should contain:

* A django migration that verifies all couch docs have been migrated and cleans up any stragglers, using the `auto-managed migration pattern <https://commcare-hq.readthedocs.io/migration_command_pattern.html#auto-managed-migration-pattern>`_. `Sample commit for Dhis2Connection <https://github.com/dimagi/commcare-hq/pull/26400/commits/42d113a6727f3b27484cfc12a296896989e6dce9>`_.
* Replacements of all code that reads from the couch document to instead read from SQL. This is likely the most unique part of the migration. Some common patterns are `replacing couch queries with SQL queries <https://github.com/dimagi/commcare-hq/pull/26400/commits/e270e5c1fb932c850b6a356208f1ff6ae0e06299>`_ and `unpacking code that takes advantage of couch docs being json <https://github.com/dimagi/commcare-hq/pull/26400/commits/f04afe870f92293074fb1f6127c716330dabdc36>`_.

For models with many references, it may make sense to do this work incrementally, with a first PR that includes the verification migration and then subsequent PRs that update a subset of reads.

This PR is a good time to do QA. So that both migrated objects and new objects get tested, ask the QA team to set up some couch docs on staging before you deploy anything. Then deploy PR 1, run the migration command, deploy PR 2, and ask QA to test both the old objects and to create and test some new objects.

PR 3: 
****
This is the cleanup PR. Wait a few days or weeks after the previous PR to merge this one; there's no rush. Clean up:

* Remove the old couch model. `Sample commit for Dhis2Connection <https://github.com/dimagi/commcare-hq/pull/26400/commits/fea7f38abb24f8b3a00f382fb9e2cdcbdd43f972>`_.
* Add the couch class to `deletable_doc_types <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/cleanup/deletable_doc_types.py>`_. `Sample commit for Dhis2Connection <https://github.com/dimagi/commcare-hq/pull/26400/commits/2004a8f1a6fd38789df719b8a8ab992ffc44d8dc>`_.
* Remove any couch views that are no longer used. Remember this may require a reindex; see the `main db migration docs <https://commcare-hq.readthedocs.io/migrations.html>`_
