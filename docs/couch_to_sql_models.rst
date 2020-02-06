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

A note on source control: it's best to create all pull requests at once so that reviewers have full context on the migration. It's easier to do the work in a single branch and then make the branches for individual PRs later on. If you don't typically run a linter before PRing, let the linter run on each PR and fix errors before opening the next one.

PR 1: Add SQL model and migration management command, write to SQL
****
This should contain:

* A new model, with a django migration to create it.

  * Expect to rename your model laster, and specify ``db_table`` with the final expected table name. If your couch model is ``MyModel``, name your SQL model ``SQLMyModel`` with ``db_table`` set to ``myapp_mymodel`` so that once the couch model is gone, you can rename the SQL model back to ``MyModel`` and remove the ``Meta``. It's a headache to rename models via django migrations, especially submodels.
  * `Sample commit for RegistrationRequest <https://github.com/dimagi/commcare-hq/pull/26555/commits/5df642a5f798880e29d65f1a389d4c068aaa47c3>`_, a simple model with no related models. This example pulls functions common to booth couch and sql into a mixin used by both classes.
  * It's frequently useful to include a column for the corresponding couch document id. The `HqDeploy migration <https://github.com/dimagi/commcare-hq/pull/26440/files>`_ does this (search for `couch_id`).
  * Note that by default, the sql fields will be non-null. Boilerplate to run on production to identify which attributes are null in actual documents, using ``HqDeploy`` as an example (note this loads all docs into memory):
  ::
  
    from corehq.dbaccessors.couchapps.all_docs import get_all_docs_with_doc_types
    from corehq.apps.hqadmin.models import HqDeploy
    attrs = ['environment', 'user', 'date']
    docs = list(get_all_docs_with_doc_types(HqDeploy.get_db(), ['HqDeploy']))
    [(attr, len([d for d in docs if not doc.get(attr)])) for attr in attrs]

* A standalone management command that fetches all couch docs and creates a corresponding SQL model if it doesn't already exist.

  * The base class ``PopulateSQLCommand`` makes this fairly trivial for simple models.
  * `Sample commit for RegistrationRequest <https://github.com/dimagi/commcare-hq/pull/26555/commits/e8639003899d9e10fb9fc2cd7388df843104b5e1>`_.
  * Don't know which database your doc type is in? Run ``from corehq.util.couchdb_management import couch_config; couch_config.all_dbs_by_slug`` in a shell to list all of the couch databases and then ``MyModel.get_db()`` to see which one you need.
  
* Adds code to keep the couch and sql items in sync.

  * In the simple cases, this is just a matter of updating the ``save`` methods for both couch and sql to save themselves and also either find and update or create the corresponding item. `Sample commit for RegistrationRequest <https://github.com/dimagi/commcare-hq/pull/26555/commits/a157aa456850f1c1d076581035b273e6394d132a>`_.
  * The `SyncCouchToSQLMixin <https://github.com/dimagi/commcare-hq/blob/c2b93b627c830f3db7365172e9be2de0019c6421/corehq/ex-submodules/dimagi/utils/couch/migration.py#L4>`_ and `SyncSQLToCouchMixin <https://github.com/dimagi/commcare-hq/blob/c2b93b627c830f3db7365172e9be2de0019c6421/corehq/ex-submodules/dimagi/utils/couch/migration.py#L115>`_ also exist for this purpose.

* Most models belong to a domain. These models need to be deleted when the domain is deleted.

  * Add the new model to `DOMAIN_DELETE_OPERATIONS <https://github.com/dimagi/commcare-hq/blob/522294560cee0f3ac1ddeae0501d653b1ea0f215/corehq/apps/domain/deletion.py#L179>`_.
  * Update tests in `test_delete_domain.py`. `Sample PR that handles several app manager models <https://github.com/dimagi/commcare-hq/pull/26310/files>`_.
  
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
  * `Sample commit for RegistrationRequest <https://github.com/dimagi/commcare-hq/pull/26556/commits/6a55c47d7d6ee21b9762e250d968968859d98166>`_.
* Replacements of all code that reads from the couch document to instead read from SQL. This is likely the most unique part of the migration. Some patterns are:

  * `Replacing couch queries with SQL queries <https://github.com/dimagi/commcare-hq/pull/26400/commits/e270e5c1fb932c850b6a356208f1ff6ae0e06299>`_
  * `Unpacking code that takes advantage of couch docs being json <https://github.com/dimagi/commcare-hq/pull/26400/commits/f04afe870f92293074fb1f6127c716330dabdc36>`_.

For models with many references, it may make sense to do this work incrementally, with a first PR that includes the verification migration and then subsequent PRs that each update a subset of reads. Throughout this phase, all data should continue to be saved to both couch and sql.

After testing locally, this PR is a good time to ask the QA team to test on staging. Template for QA request notes:

::

    This is a couch to sql migration, with the usual approach:
    - Set up <workflow to create items in couch>.
    - Ping me on the ticket and I'll deploy the code to staging and run the migration
    - Test that you can <workflows to edit the items created earlier> and also <workflow to create new items>.

PR 3: 
****
This is the cleanup PR. Wait a few days or weeks after the previous PR to merge this one; there's no rush. Clean up:

* If your sql model uses a ``couch_id``, remove it. `Sample commit for HqDeploy <https://github.com/dimagi/commcare-hq/pull/26442/commits/3fa10a6a511b0b592979cc4183d84d3a4e36f200>`_.
* Remove the old couch model, which at this point should have no references.
* Now that the couch model is gone, rename the sql model from ``SQLMyModel`` to ``MyModel``. Assuming you set up ``db_table`` in the initial PR, this should include removing the sql model's ``Meta`` class and adding a small django migration. `Sample commit for RegistrationRequest <https://github.com/dimagi/commcare-hq/pull/26557/commits/beb9d10f6d8d0906524912ef94a8d049f06c38e8>`_.
* Add the couch class to ``DELETABLE_COUCH_DOC_TYPES``. `Sample commit for Dhis2Connection <https://github.com/dimagi/commcare-hq/pull/26400/commits/2a6e93e19ab689cfaf0b4cdc89c9039cbee33139>`_.
* Remove any couch views that are no longer used. Remember this may require a reindex; see the `main db migration docs <https://commcare-hq.readthedocs.io/migrations.html>`_
