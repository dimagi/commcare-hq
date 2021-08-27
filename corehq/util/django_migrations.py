import os
import sys
import traceback
from functools import wraps

from django.conf import settings
from django.core.management import call_command
from django.db import migrations
from django.db.backends.postgresql.schema import DatabaseSchemaEditor
from django.db.migrations import RunPython


def add_if_not_exists(string):
    """
    turn a 'CREATE INDEX' template into a 'CREATE INDEX IF NOT EXISTS' template

    in PostgreSQL 9.5 it would be
         return string.replace('CREATE INDEX', 'CREATE INDEX IF NOT EXISTS')
    but the current implementation does the same thing for 9.4+

    """
    # this workaround was adapted and expanded from
    # http://dba.stackexchange.com/questions/35616/create-index-if-it-does-not-exist/35626#35626
    # The following basically means "if not exists":
    #     IF (SELECT to_regclass('%(name)s') is NULL)
    # and the 'DO $do$ BEGIN ... END $do' stuff
    # is just to make postgres allow the IF statement
    return ''.join([
        "DO $do$ BEGIN IF (SELECT to_regclass('%(name)s') is NULL) THEN ",
        string,
        "; END IF; END $do$"
    ])


def add_if_not_exists_raw(string, name):
    """
    turn a 'CREATE INDEX' template into a 'CREATE INDEX IF NOT EXISTS' template

    in PostgreSQL 9.5 it would be
         return string.replace('CREATE INDEX', 'CREATE INDEX IF NOT EXISTS')
    but the current implementation does the same thing for 9.4+

    """
    # this workaround was adapted and expanded from
    # http://dba.stackexchange.com/questions/35616/create-index-if-it-does-not-exist/35626#35626
    # The following basically means "if not exists":
    #     IF (SELECT to_regclass('%(name)s') is NULL)
    # and the 'DO $do$ BEGIN ... END $do' stuff
    # is just to make postgres allow the IF statement
    return ''.join([
        "DO $do$ BEGIN IF (SELECT to_regclass('{}') is NULL) THEN ".format(name),
        string,
        "; END IF; END $do$"
    ])


class DatabaseSchemaEditorIfNotExists(DatabaseSchemaEditor):
    sql_create_index = add_if_not_exists(DatabaseSchemaEditor.sql_create_index)
    sql_create_unique = add_if_not_exists(DatabaseSchemaEditor.sql_create_unique)
    # can remove the following lines once we're on Django 2.x
    # they're internals whose usage within Django was replaced
    if hasattr(DatabaseSchemaEditor, 'sql_create_varchar_index'):
        sql_create_varchar_index = add_if_not_exists(DatabaseSchemaEditor.sql_create_varchar_index)
    if hasattr(DatabaseSchemaEditor, 'sql_create_text_index'):
        sql_create_text_index = add_if_not_exists(DatabaseSchemaEditor.sql_create_text_index)


class AlterIndexIfNotExists(migrations.AlterIndexTogether):

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        schema_editor.__class__ = DatabaseSchemaEditorIfNotExists
        try:
            super(AlterIndexIfNotExists, self).database_forwards(
                app_label, schema_editor, from_state, to_state)
        finally:
            schema_editor.__class__ = DatabaseSchemaEditor


class AlterFieldCreateIndexIfNotExists(migrations.AlterField):

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        schema_editor.__class__ = DatabaseSchemaEditorIfNotExists
        try:
            super(AlterFieldCreateIndexIfNotExists, self).database_forwards(
                app_label, schema_editor, from_state, to_state)
        finally:
            schema_editor.__class__ = DatabaseSchemaEditor


class AlterUniqueTogetherIfNotExists(migrations.AlterUniqueTogether):
    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        schema_editor.__class__ = DatabaseSchemaEditorIfNotExists
        try:
            super(AlterUniqueTogetherIfNotExists, self).database_forwards(
                app_label, schema_editor, from_state, to_state)
        finally:
            schema_editor.__class__ = DatabaseSchemaEditor


def skip_on_fresh_install(migration_fn):
    """Skips the migration if setting up a blank database"""
    @wraps(migration_fn)
    def _inner(*args, **kwargs):
        if settings.UNIT_TESTING or os.environ.get('CCHQ_IS_FRESH_INSTALL') == '1':
            return
        return migration_fn(*args, **kwargs)
    return _inner


def noop_migration():
    """
    Used as a fallback when dynamically determining whether to run a migration
    Old migrations can be simply removed. `operations = []` is perfectly valid
    """
    return RunPython(RunPython.noop, RunPython.noop)


def run_once_off_migration(command_name, *args, required_commit=None, **kwargs):
    """Return a migration operation that can be used to run a management command from
    a Django migration. This will give the user directions for running the command
    manually if the command fails or has since been removed from the codebase"""
    @skip_on_fresh_install
    def _run_command(apps, schema_editor):
        run_management_command_or_exit(command_name, required_commit, *args, **kwargs)

    return migrations.RunPython(_run_command, reverse_code=migrations.RunPython.noop, elidable=True)


def run_management_command_or_exit(command_name, *args, required_commit=None, custom_message=None, **kwargs):
    """Helper function to run a management command automatically and abort if there was an error
    with helpful console output to allow users to run it manually if it fails or
    has since been removed from the codebase."""
    try:
        call_command(command_name, *args, **kwargs)
    except Exception:
        traceback.print_exc()
        print(f"""
            A migration must be performed before this environment can be upgraded to the latest version
            of CommCareHQ. This migration is run using the management command {command_name}.
        """)
        if required_commit or custom_message:
            print("")
            print(custom_message or f"""
            Run the following commands to run the migration and get up to date:

                commcare-cloud <env> fab setup_limited_release --set code_branch={required_commit}

                commcare-cloud <env> django-manage --release <release created by previous command> {command_name}

                commcare-cloud <env> deploy commcare
            """)
        sys.exit(1)


def block_upgrade_for_removed_migration(commit_with_migration):
    """Returns a Django migration operation that will block the upgrade if the migration
    has not run (fresh installs will not get blocked).

    :param commit_with_migration: A Git commit hash that contains the migration.
    """
    @skip_on_fresh_install
    def show_message(apps, schema_editor):
        print("""
            A migration must be performed before this environment can be upgraded to the latest version
            of CommCareHQ. The migration has been removed from the current version of the code so an older
            version must be used.
        """)
        print("")
        print("""
        Run the following commands to run the migration and get up to date:

            commcare-cloud <env> fab setup_limited_release --set code_branch={commit_with_migration}

            commcare-cloud <env> django-manage --release <release created by previous command> migrate_multi

            commcare-cloud <env> deploy commcare
        """)
        sys.exit(1)

    return migrations.RunPython(show_message, reverse_code=migrations.RunPython.noop, elidable=True)
