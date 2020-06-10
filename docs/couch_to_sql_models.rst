.. _couch-to-sql-model-migration:

***************************************
Migrating models from couch to postgres
***************************************

This is a step by step guide to migrating a single model from couch to postgres.

Selecting a Model
################

To find all classes that descend from ``Document``:
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

Some notes on source control:

  * It's best to create all pull requests at once so that reviewers have full context on the migration.
  * It can be easier to do the work in a single branch and then make the branches for individual PRs later on.
  * If you don't typically run a linter before PRing, let the linter run on each PR and fix errors before opening the next one.
  * Avoid having more than one migration happening in the same django app at the same time, to avoid migration conflicts.

PR 1: Add SQL model and migration management command, write to SQL
****
This should contain:

* A new model and a management command that fetches all couch docs and creates or updates the corresponding SQL model(s).

  * Start by running the management command ``evaluate_couch_model_for_sql django_app_name MyDocType`` on a production environment. This will produce code to add to your models file and also a new management command.
  * Add the generated models code to your models file. Note if there are any TODOs marked in the code. Notes on this code:
     * The new class will start with "SQL" but specify ``db_table`` so that prefix can be easily removed later and ``db_table`` removed. It's a headache to rename models via django migrations, especially submodels.
     * The new class will include a column for the corresponding couch document id.
     * The generated code does not include submodel classes (SchemaProperty or SchemaListProperty attributes). See `the first CustomDataFieldsDefinition PR <https://github.com/dimagi/commcare-hq/pull/27276>`_ for an example that uses submodels.
     * The generated code uses `SyncCouchToSQLMixin <https://github.com/dimagi/commcare-hq/blob/c2b93b627c830f3db7365172e9be2de0019c6421/corehq/ex-submodules/dimagi/utils/couch/migration.py#L4>`_ and `SyncSQLToCouchMixin <https://github.com/dimagi/commcare-hq/blob/c2b93b627c830f3db7365172e9be2de0019c6421/corehq/ex-submodules/dimagi/utils/couch/migration.py#L115>`_. If your model uses submodels, you will need to add overrides for ``_migration_sync_to_sql`` and ``_migration_sync_to_couch``.
        * Beware that the sync mixins capture exceptions thrown while syncing in favor of calling ``notify_exception``. If you're overwriting the sync code, this makes bugs easy to miss. The branch ``jls/sync-mixins-hard-fail`` is included on staging to instead make syncing fail hard; you might consider doing the same while testing locally.
     * Consider if your new model could use any additional ``db_index`` flags or a ``unique_together``.
     * Some docs have attributes that are couch ids of other docs. These are weak spots easy to forget when the referenced doc type is migrated. Add a comment so these show up in a grep for the referenced doc type.
  * Run `makemigrations`
  * Add the generated migration command. Notes on this code:
     * The generated migration does not handle submodels. Edit ``update_or_create_sql_object`` to add support.
     * This command should populate the sql models based on the json from couch alone, not the wrapped document (to avoid introducing another dependency on the couch model). You may need to convert data types that the default ``wrap`` implementation would handle. The generated migration will use ``force_to_datetime`` to cast datetimes but will not perform any other wrapping.
     * The command will include a ``commit_adding_migration`` method to let third parties know which commit to deploy if they need to run the migration manually. This needs to be updated **after** this PR is merged, to add the hash of the commit that merged this PR into master.

* Most models belong to a domain. For these:

  * Add the new model to `DOMAIN_DELETE_OPERATIONS <https://github.com/dimagi/commcare-hq/blob/522294560cee0f3ac1ddeae0501d653b1ea0f215/corehq/apps/domain/deletion.py#L179>`_ so it gets deleted when the domain is deleted.
  * Update tests in `test_delete_domain.py`. `Sample PR that handles several app manager models <https://github.com/dimagi/commcare-hq/pull/26310/files>`_.
  * Add the new model to `sql/dump.py <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/dump_reload/sql/dump.py>`_ so that it gets included when a domain is exported.

To test this step locally:

* With master checked out, make sure you have at least one couch document that will get migrated.
* Check out your branch and run the populate command. Verify it creates as many objects as expected.
* Test editing the pre-existing object. In a shell, verify your changes appear in both couch and sql.
* Test creating a new object. In a shell, verify your changes appear in both couoch and sql.

Once this PR is deployed, run the migration command in any environments where it's likely to take more than a trivial amount of time.

PR 2: Verify migration and read from SQL
****
This should contain:

* A django migration that verifies all couch docs have been migrated and cleans up any stragglers, using the `auto-managed migration pattern <https://commcare-hq.readthedocs.io/migration_command_pattern.html#auto-managed-migration-pattern>`_.

  * This should be trivial, since all the work is done in the populate command from the previous PR.
  * `Sample migration for RegistrationRequest <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/registration/migrations/0003_populate_sqlregistrationrequest.py>`_.
* Replacements of all code that reads from the couch document to instead read from SQL. This is the hard part: finding **all** usages of the couch model and updating them as needed to work with the sql model. Some patterns are:

  * `Replacing couch queries with SQL queries <https://github.com/dimagi/commcare-hq/pull/26400/commits/e270e5c1fb932c850b6a356208f1ff6ae0e06299>`_
  * `Unpacking code that takes advantage of couch docs being json <https://github.com/dimagi/commcare-hq/pull/26400/commits/f04afe870f92293074fb1f6127c716330dabdc36>`_.
  * Replacing ``get_id`` with ``id`` - including in HTML templates - and ``MyModel.get(ID)`` with ``SQLMyModel.objects.get(id=ID)``.

For models with many references, it may make sense to do this work incrementally, with a first PR that includes the verification migration and then subsequent PRs that each update a subset of reads. Throughout this phase, all data should continue to be saved to both couch and sql.

After testing locally, this PR is a good time to ask the QA team to test on staging. Template for QA request notes:

::

    This is a couch to sql migration, with the usual approach:
    - Set up <workflow to create items in couch>.
    - Ping me on the ticket and I'll deploy the code to staging and run the migration
    - Test that you can <workflows to edit the items created earlier> and also <workflow to create new items>.

PR 3: 
****
This is the cleanup PR. Wait a few weeks after the previous PR to merge this one; there's no rush. Clean up:

* If your sql model uses a ``couch_id``, remove it. `Sample commit for HqDeploy <https://github.com/dimagi/commcare-hq/pull/26442/commits/3fa10a6a511b0b592979cc4183d84d3a4e36f200>`_.
* Remove the old couch model, which at this point should have no references. This includes removing any syncing code.
* Now that the couch model is gone, rename the sql model from ``SQLMyModel`` to ``MyModel``. Assuming you set up ``db_table`` in the initial PR, this should include removing the sql model's ``Meta`` class and adding a small django migration. `Sample commit for RegistrationRequest <https://github.com/dimagi/commcare-hq/pull/26557/commits/beb9d10f6d8d0906524912ef94a8d049f06c38e8>`_.
* Add the couch class to ``DELETABLE_COUCH_DOC_TYPES``. `Sample commit for Dhis2Connection <https://github.com/dimagi/commcare-hq/pull/26400/commits/2a6e93e19ab689cfaf0b4cdc89c9039cbee33139>`_.
* Remove any couch views that are no longer used. Remember this may require a reindex; see the `main db migration docs <https://commcare-hq.readthedocs.io/migrations.html>`_
