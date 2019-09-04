.. _auto-managed-migration-pattern:

Auto-Managed Migration Pattern
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A re-entrant data migration management command can be a useful way to perform
large-scale data migrations in environments where the migration takes a long
time to complete due to the volume of data being migrated. A management command
is better than a simple Django migration because it can be designed to be
stopped and started as many times as necessary until all data has been migrated.
Obviously the migration must be performed prior to the deployment of any code
depending on the finished migration, so it must be applied to all environments
before that can happen.

However, it would be tedious and error prone to require everyone running smaller
CommCareHQ environments, including developers who are working on other parts of
the project, to learn about and follow the painstaking manual process used to
migrate large environments. This document outlines a pattern that can be used to
ensure a smooth rollout to everyone running any size environment with minimal
overhead for those running small environments.


Pattern Components
------------------

- A management command that performs the data migration.

  - Unless downtime will be scheduled, the command should be written in a way
    that allows legacy code to continue working while the migration is in
    progress. Techniques for achieving this are out of scope here.
  - May accept a ``--dbname=xxxx`` parameter to limit operation to the
    given database.

- Change log entry in CommCare Cloud describing the steps to perform the
  migration manually by running the management command.
- A Django migration that will

  - Check if there are any items that need to be migrated
  - Run the management command if necessary
  - Verify management command success/failure
  - Display an error and stop on failure
  - Continue with next migration on success


Django Migration Code Example
-----------------------------

Edit as necessary to fit your use case. The constants at the top and the
migration dependencies are the most important things to review/change.

This example does a migration that only affects SQL data, but that is not
required. It is also possible to apply this pattern to migrations on non-SQL
databases as long as the necessary checks (does the migration need to be run?
did it run successfully?) can be performed in the context of a Django migration.


.. code-block:: python

    import sys
    import traceback

    from django.core.management import call_command
    from django.db import migrations

    from corehq.util.django_migrations import skip_on_fresh_install


    COUNT_ITEMS_TO_BE_MIGRATED = "SELECT COUNT(*) FROM ..."
    GIT_COMMIT_WITH_MANAGEMENT_COMMAND = "TODO change this"
    AUTO_MIGRATE_ITEMS_LIMIT = 10000
    AUTO_MIGRATE_FAILED_MESSAGE = """
    A migration must be performed before this environment can be upgraded to the
    latest version of CommCareHQ. Instructions for running the migration can be
    found at this link:

    https://github.com/dimagi/commcare-cloud/blob/master/docs/changelog/0000-example-entry.md

    You will need to checkout an older version of CommCareHQ first if you are
    unable to run the management command because it has been deleted:

    git checkout {commit}
    """.format(commit=GIT_COMMIT_WITH_MANAGEMENT_COMMAND)


    @skip_on_fresh_install
    def _assert_migrated(apps, schema_editor):
        """Check if migrated. Raises SystemExit if not migrated"""
        num_items = count_items_to_be_migrated(schema_editor.connection)

        migrated = num_items == 0
        if migrated:
            return

        if num_items < AUTO_MIGRATE_ITEMS_LIMIT:
            try:
                call_command(
                    "the_migration_management_command",
                    dbname=schema_editor.connection.alias,
                )
                migrated = count_items_to_be_migrated(schema_editor.connection) == 0
                if not migrated:
                    print("Automatic migration failed")
            except Exception:
                traceback.print_exc()
        else:
            print("Found %s items that need to be migrated." % num_items)
            print("Too many to migrate automatically.")

        if not migrated:
            print("")
            print(AUTO_MIGRATE_FAILED_MESSAGE)
            sys.exit(1)


    def count_items_to_be_migrated(connection):
        """Return the number of items that need to be migrated"""
        with connection.cursor() as cursor:
            cursor.execute(COUNT_ITEMS_TO_BE_MIGRATED)
            return cursor.fetchone()[0]


    class Migration(migrations.Migration):

        dependencies = [
            ...
        ]

        operations = [
            migrations.RunPython(_assert_migrated, migrations.RunPython.noop)
        ]


Real-life example
-----------------

`XForm attachments to blob metadata migration 
<https://github.com/dimagi/commcare-hq/blob/73f08b5da1b4eaa4cf1f804830c780d96742c9ff/corehq/form_processor/migrations/0078_blobmeta_migrated_check.py>`_.

