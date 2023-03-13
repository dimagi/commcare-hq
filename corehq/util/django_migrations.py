import os
import sys
from contextlib import contextmanager
from datetime import datetime
from functools import wraps

from django.apps import apps
from django.conf import settings
from django.db import migrations
from django.db.backends.postgresql.schema import DatabaseSchemaEditor
from django.db.migrations import RunPython

from django.db.migrations.autodetector import MigrationAutodetector
from django.db.migrations.recorder import MigrationRecorder


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


def execute_sql_if_exists_raw(string, name):
    """
    turn a 'TRUNCATE TABLE' template into a 'TRUNCATE TABLE IF EXISTS' template
    """
    return ''.join([
        "DO $do$ BEGIN IF NOT (SELECT to_regclass('{}') is NULL) THEN ".format(name),
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


def prompt_for_historical_migration(app_name, migration_name, required_commit):
    """Returns a migration operation that will prompt the user to run a migration from a previous
    version of the code. Note that this operation is never intended to succeed, because the code
    needed for the migration no longer exists"""

    def get_most_recent_migration_date():
        return MigrationRecorder.Migration.objects \
            .order_by('-applied') \
            .values_list('applied') \
            .first()[0]

    def get_days_since_last_migration():
        current_time = datetime.now()
        last_migration_time = get_most_recent_migration_date()

        return (current_time - last_migration_time).days

    @skip_on_fresh_install
    def _run_command(apps, schema_editor):
        print("")
        print(f"""
        This migration cannot be run, as it depends on code that has since been removed.
        To fix this, follow the instructions below to run this migration from a previous version of the code.
        In order to prevent this in the future, we recommend running migrations at least once every 6 weeks.
        For reference, the current code has not run migrations for {get_days_since_last_migration()} days.

        Run the following commands to run the historical migration and get up to date:
            With a cloud setup:
                commcare-cloud <env> fab setup_limited_release --set code_branch={required_commit}

                commcare-cloud <env> django-manage --release <release created by previous command> migrate_multi {app_name}

                commcare-cloud <env> deploy commcare

            With a development setup:
                git checkout {required_commit}
                ./manage.py migrate_multi {app_name}

        If you are sure this migration is unnecessary, you can fake the migration:
            With a cloud setup:
                commcare-cloud <env> django-manage migrate_multi --fake {app_name} {migration_name}

            With a development setup:
                ./manage.py migrate_multi --fake {app_name} {migration_name}
        """)  # noqa: E501
        sys.exit(1)

    return migrations.RunPython(_run_command, reverse_code=migrations.RunPython.noop)


def get_migration_name(file_path):
    return os.path.splitext(os.path.basename(file_path))[0]


@contextmanager
def patch_migration_autodetector(makemigrations_command):
    """Allow app configs to participate in migration auto-detection

    AppConfig migration contributions are made after other Django
    migration operations have been detected.

    AppConfigs that implement ``autodetect_migrations(add_operation)``
    may contribute to migration autodetection. The ``add_operation``
    callable argument accepts the same arguments as
    ``MigrationAutodetector.add_operation``. ``autodetect_migrations``
    may return a function, which will be called during the
    ``write_migration_files`` phase of migration generation.

    This patch is intended to be applied when calling the ``handle`` method
    of ``django.core.management.commands.makemigrations.Command``.
    """
    def _detect_changes(self, convert_apps=None, graph=None):
        def _sort_migrations(self):
            if convert_apps:
                configs = [apps.get_app_config(label) for label in convert_apps]
            else:
                configs = apps.get_app_configs()
            for app in configs:
                try:
                    detect_changes = app.autodetect_migrations
                except AttributeError:
                    continue
                write_files = detect_changes(self.add_operation)
                if write_files is not None:
                    write_ops.append(write_files)
            return real_sort_migrations(self)

        with _patch(MigrationAutodetector, "_sort_migrations", _sort_migrations):
            return real_detect_changes(self, convert_apps=convert_apps, graph=graph)

    def write_files(changes):
        result = real_write_files(changes)
        if not makemigrations_command.dry_run:
            for write_op in write_ops:
                write_op()
        write_ops.clear()
        return result

    write_ops = []
    real_detect_changes = MigrationAutodetector._detect_changes
    real_sort_migrations = MigrationAutodetector._sort_migrations
    real_write_files = makemigrations_command.write_migration_files
    with (
        _patch(MigrationAutodetector, "_detect_changes", _detect_changes),
        _patch(makemigrations_command, "write_migration_files", write_files),
    ):
        yield


@contextmanager
def _patch(obj, attribute, value):
    original = getattr(obj, attribute)
    setattr(obj, attribute, value)
    try:
        yield
    finally:
        setattr(obj, attribute, original)
