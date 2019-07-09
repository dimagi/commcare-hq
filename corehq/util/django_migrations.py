from __future__ import absolute_import, unicode_literals

import os
from functools import wraps

from django.conf import settings
from django.db import migrations
from django.db.backends.postgresql_psycopg2.schema import DatabaseSchemaEditor
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
    sql_create_varchar_index = add_if_not_exists(DatabaseSchemaEditor.sql_create_varchar_index)
    sql_create_text_index = add_if_not_exists(DatabaseSchemaEditor.sql_create_text_index)
    sql_create_unique = add_if_not_exists(DatabaseSchemaEditor.sql_create_unique)


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
