.. _couch-to-sql-model-migration:

***************************************
Migrating models from couch to postgres
***************************************

This is a step by step guide to migrating a single model from couch to postgres.

Conceptual Steps
################

This is a multi-deploy process that keeps two copies of the data - one in couch, one in sql - in sync until the final piece of code is deployed and the entire migration is complete.
It has three phases:

1. Add SQL models and sync code

   * Define the new SQL models, based on the existing couch classes and using the `SyncSQLToCouchMixin <https://github.com/dimagi/commcare-hq/blob/c2b93b627c830f3db7365172e9be2de0019c6421/corehq/ex-submodules/dimagi/utils/couch/migration.py#L115>`_ to keep sql changes in sync with couch.
   * Add the `SyncCouchToSQLMixin <https://github.com/dimagi/commcare-hq/blob/c2b93b627c830f3db7365172e9be2de0019c6421/corehq/ex-submodules/dimagi/utils/couch/migration.py#L4>`_ to the couch class so that changes to couch documents get reflected in sql.
   * Write a management command that subclasses `PopulateSQLCommand <https://github.com/dimagi/commcare-hq/blob/500040985e0aaffa9a220c65e81318a1afa4761b/corehq/apps/cleanup/management/commands/populate_sql_model_from_couch_model.py#L15>`_, which will create/update a corresponding SQL object for every couch document. This command will later be run by a django migration to migrate the data. For large servers, this command will also need to be run manually, outside of a deploy, to do the bulk of the migration.

2. Switch app code to read/write in SQL

   * Update all code references to the couch classes to instead refer to the SQL classes.
   * Write a django migration that integrates with ``PopulateSQLCommand`` to ensure that all couch and sql data is synced.

3. Remove couch

   * Delete the couch classes, and remove the ``SyncSQLToCouchMixin`` from the SQL classes.

Practical Steps
###############

Even a simple model takes several pull requests to migrate, to avoid data loss while deploys and migrations are in progress. Best practice is a minimum of three pull requests, described below, each deployed to all large environments before merging the next one.

Some notes on source control:

* It's best to create all pull requests at once so that reviewers have full context on the migration.
* It can be easier to do the work in a single branch and then make the branches for individual PRs later on.
* If you don't typically run a linter before PRing, let the linter run on each PR and fix errors before opening the next one.
* Avoid having more than one migration happening in the same django app at the same time, to avoid migration conflicts.

PR 1: Add SQL model and migration management command, write to SQL
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
This should contain:

- A new model and a management command that fetches all couch docs and creates or updates the corresponding SQL model(s).

  - Start by running the management command ``evaluate_couch_model_for_sql django_app_name MyDocType`` on a production environment. This will produce code to add to your models file, a new management command and also a test which will ensure that the couch model and sql model have the same attributes.

    - The reason to run on production is that it will examine existing documents to help determine things like ``max_length``. This also means it can take a while. If you have reasonable data locally, running it locally is fine - but since the sql class will often have stricter data validation than couch, it's good to run it on prod at some point.

    - If the script encounters any list or dict properties, it'll ask you if they're submodels. If you say no, it'll create them as json columns. If you say yes, it'll skip them, because it doesn't currently handle submodels. For the same reason, it'll skip SchemaProperty and SchemaListProperty attributes. More on this subject below.

    - Properties found on documents in Couch that are not members of the Couch model class will be added to the SQL model. In most cases they can be dropped (and not migrated to SQL).

    - Properties that are present in the Couch model, but always ``null`` or not found in Couch will be added to the SQL model as ``unknown_type(null=True)``. These fields may be able to be dropped (and not migrated to SQL).

  - Add the generated models code to your models file. Edit as needed. Note the TODOs marked in the code:

    - The new class's name will start with "SQL" but specify  table name ``db_table`` that does not include "sql." This is so that the class can later be renamed back to the original couch class's name by just removing the ``db_table``. This avoids renaming the table in a django migration, which can be a headache when submodels are involved.

    - The new class will include a column for couch document id.

    - The generated code uses `SyncCouchToSQLMixin <https://github.com/dimagi/commcare-hq/blob/c2b93b627c830f3db7365172e9be2de0019c6421/corehq/ex-submodules/dimagi/utils/couch/migration.py#L4>`_ and `SyncSQLToCouchMixin <https://github.com/dimagi/commcare-hq/blob/c2b93b627c830f3db7365172e9be2de0019c6421/corehq/ex-submodules/dimagi/utils/couch/migration.py#L115>`_.  If your model uses submodels, you will need to add overrides for ``_migration_sync_to_sql`` and ``_migration_sync_to_couch``. If you add overrides, definitely add tests for them. Sync bugs are one of the easiest ways for this to go terribly wrong.

      - For an example of overriding the sync code for submodels, see the `CommtrackConfig migration <https://github.com/dimagi/commcare-hq/pull/27597/>`_, or the `CustomDataFields migration <https://github.com/dimagi/commcare-hq/pull/27276/>`_ which is simpler but includes a P1-level bug fixed `here <https://github.com/dimagi/commcare-hq/pull/28001/>`__.

      - Beware that the sync mixins capture exceptions thrown while syncing in favor of calling ``notify_exception``. If you're overwriting the sync code, this makes bugs easy to miss. The branch ``jls/sync-mixins-hard-fail`` is included on staging to instead make syncing fail hard; you might consider doing the same while testing locally.

    - Consider if your new model could use any additional ``db_index`` flags or a ``unique_together``.

    - Some docs have attributes that are couch ids of other docs. These are weak spots easy to forget when the referenced doc type is migrated. Add a comment so these show up in a grep for the referenced doc type.

  - Run ``makemigrations``
  - Add the test that was generated to it's respective place.
    - The test file uses a `ModelAttrEquality` util which has methods for running the equality tests.
    - The test class that is generated will have two attributes  `couch_only_attrs`, `sql_only_attrs` and one method `test_have_same_attrs`.
    - Generally during a migration some attributes and methods are renamed or removed as per need. To accomodate the changes you can update `couch_only_attrs` and `sql_only_attrs`.
    - `couch_only_attrs` should be a set of attributes and methods which are either removed, renamed or not used anymore in SQL.
    - `sql_only_attrs` should be a set of attributes and methods that are new in the SQL model.
    - `test_have_same_attrs` will test the equality of the attributes. The default implementation should work if you have populated `couch_only_attrs` and `sql_only_attrs` but you can modify it's implementation as needed.
  - Add the generated migration command. Notes on this code:

    - The generated migration does not handle submodels. Support for submodels with bulk migrations might just work, but you should test and verify to ensure that it does. Legacy migrations that implement ``update_or_create_sql_object`` should handle submodels in that method.

    - Legacy mode: each document is saved individually rather than in bulk when ``update_or_create_sql_object`` is implemented. ``update_or_create_sql_object`` populates the sql models based on json alone, not the wrapped document (to avoid introducing another dependency on the couch model). You may need to convert data types that the default ``wrap`` implementation would handle. The generated migration will use ``force_to_datetime`` to cast datetimes but will not perform any other wrapping. Similarly, if the couch class has a ``wrap`` method, the migration needs to manage that logic. As an example, ``CommtrackActionConfig.wrap`` was defined `here <https://github.com/dimagi/commcare-hq/commit/03f1d18fac311e71a19747a035155f9121b7a869>`__ and handled in `this migration <https://github.com/dimagi/commcare-hq/pull/27597/files#diff-10eba0437b0d32b2a455e5836dc4bd93f4297c9c9d89078334f31d9eacda2258R113>`_. **WARNING**: migrations that use ``update_or_create_sql_object`` have a race condition.

      - A normal HQ operation loads a Couch document.
      - A ``PopulateSQLCommand`` migration loads the same document in a batch of 100.
      - The HQ operation modifies and saves the Couch document, which also syncs changes to SQL (the migration's copy of the document is now stale).
      - The migration calls ``update_or_create_sql_object`` which overwrites above changes, reverting SQL to the state of its stale Couch document.

    - The command will include a ``commit_adding_migration`` method to let third parties know which commit to deploy if they need to run the migration manually. This needs to be updated **after** this PR is merged, to add the hash of the commit that merged this PR into master.

- Most models belong to a domain. For these:

  - Add the new model to `DOMAIN_DELETE_OPERATIONS <https://github.com/dimagi/commcare-hq/blob/522294560cee0f3ac1ddeae0501d653b1ea0f215/corehq/apps/domain/deletion.py#L179>`_ so it gets deleted when the domain is deleted.

  - Update tests in `test_delete_domain.py`. `Sample PR that handles several app manager models <https://github.com/dimagi/commcare-hq/pull/26310/files>`_.

  - Add the new model to `sql/dump.py <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/dump_reload/sql/dump.py>`_ so that it gets included when a domain is exported.

To test this step locally:

- With master checked out, make sure you have at least one couch document that will get migrated.
- Check out your branch and run the populate command. Verify it creates as many objects as expected.
- Test editing the pre-existing object. In a shell, verify your changes appear in both couch and sql.
- Test creating a new object. In a shell, verify your changes appear in both couch and sql.

Automated tests are also a good idea. Automated tests are definitely necessary if you overrode any parts of the
sync mixins. `Example of tests for sync and migration code <https://github.com/dimagi/commcare-hq/pull/28042/files#diff-a1ef9cf2695fb1e0498e49c9f2643c3a>`_.

The migration command has a ``--verify`` option that will find any differences in the couch data vs the sql data.

The ``--fixup-diffs=/path/to/migration-log.txt`` option can be used to resolve differences between Couch and SQL state. Most differences reported by the migration command should be transient; that is, they will eventually be resolved by normal HQ operations, usually within a few milliseconds. **The ``--fixup-diffs`` option should only be used to fix persistent differences caused by a bug in the Couch to SQL sync logic after the bug has been fixed.** If a bug is discovered and most rows have diffs and (important!) PR 2 has not yet been merged, it may be more efficient to fix the bug, delete all SQL rows (since Couch is still the source of truth), and redo the migration.

Once this PR is deployed - later, after the whole shebang has been QAed - you'll run the migration command in any environments where it's likely to take more than a trivial amount of time.
If the model is tied to domains you should initially migrate a few selected domains using ``--domains X Y Z`` and manually
verify that the migration worked as expected before running it for all the data.

PR 2: Verify migration and read from SQL
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
This should contain:

* A django migration that verifies all couch docs have been migrated and cleans up any stragglers, using the `auto-managed migration pattern <https://commcare-hq.readthedocs.io/migration_command_pattern.html#auto-managed-migration-pattern>`_.

  * This should be trivial, since all the work is done in the populate command from the previous PR.

  * The migration does an automatic completeness check by comparing the number of documents in Couch to the number of rows in SQL. If the counts do not match then the migration is considered incomplete, and the migration will calculate the difference and either migrate the remaining documents automatically or prompt for manual action. **NOTE**: if the automatic migration route is chosen (in the case of a small difference) the migration may still take a long time if the total number of documents in Couch is large since the migration must check every document in Couch (of the relevant doc type) to see if it has been migrated to SQL. A count mismatch is more likely when documents are written (created and/or deleted) frequently. One way to work around this is to use the ``--override-is-migration-completed`` option of ``PopulateSQLCommand`` to force the migration into a completed state. **WARNING**: careless use of that option may result in an incomplete migration. It is recommended to only force a completed state just before the migration is applied (e.g., just before deploying), and after checking the counts with ``--override-is-migration-completed=check``.

  * `Sample migration for RegistrationRequest <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/registration/migrations/0003_populate_sqlregistrationrequest.py>`_.

* Replacements of all code that reads from the couch document to instead read from SQL. This is the hard part: finding **all** usages of the couch model and updating them as needed to work with the sql model. Some patterns are:

  * `Replacing couch queries with SQL queries <https://github.com/dimagi/commcare-hq/pull/26399/commits/e270e5c1fb932c850b6a356208f1ff6ae0e06299#diff-d87e129c5e1224e4b046b4872e35bf2c041788a14c74cf1cedfe0fa7ba920bc6>`_.

  * `Unpacking code that takes advantage of couch docs being json <https://github.com/dimagi/commcare-hq/pull/26399/commits/f04afe870f92293074fb1f6127c716330dabdc36>`_.

  * Replacing ``get_id`` with ``id`` - including in HTML templates, which don't typically need changes - and ``MyModel.get(ID)`` with ``SQLMyModel.objects.get(id=ID)``.

For models with many references, it may make sense to do this work incrementally, with a first PR that includes the verification migration and then subsequent PRs that each update a subset of reads. Throughout this phase, all data should continue to be saved to both couch and sql.

After testing locally, this PR is a good time to ask the QA team to test on staging. Template for QA request notes:

::

    This is a couch to sql migration, with the usual approach:
    - Set up <workflow to create items in couch>.
    - Ping me on the ticket and I'll deploy the code to staging and run the migration
    - Test that you can <workflows to edit the items created earlier> and also <workflow to create new items>.

PR 3: Cleanup
^^^^^^^^^^^^^
This is the cleanup PR. Wait a few weeks after the previous PR to merge this one; there's no rush. Clean up:

* If your sql model uses a ``couch_id``, remove it. `Sample commit for HqDeploy <https://github.com/dimagi/commcare-hq/pull/26442/commits/79a1c49013fb09fb47690ebcd0a51bc85fb1d560>`_
* Remove the old couch model, which at this point should have no references. This includes removing any syncing code.
* Now that the couch model is gone, rename the sql model from ``SQLMyModel`` to ``MyModel``. Assuming you set up ``db_table`` in the initial PR, this is just removing that and running ``makemigrations``.
* Add the couch class to ``DELETABLE_COUCH_DOC_TYPES``. `Blame deletable_doc_types.py <https://github.com/dimagi/commcare-hq/blame/74bc31910f692126f03c46a350ab8ae5700f87dd/corehq/apps/cleanup/deletable_doc_types.py>`_ for examples.
* Remove any couch views that are no longer used. Remember this may require a reindex; see the `main db migration docs <https://commcare-hq.readthedocs.io/migrations.html>`_.

Current State of Migration
##########################

The current state of the migration is available internally `here <https://docs.google.com/spreadsheets/d/1iayf898ktfSRXdjBVutj_AgH4WN9DrheMS6vgteqfFM/edit#gid=677779031>`__,
which outlines approximate LOE, risk level, and notes on the remaining models.

For a definitive account of remaining couch-based models, you can identify all classes that descend from ``Document``:
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
