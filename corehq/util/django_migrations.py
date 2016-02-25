from django.db import migrations
from django.db.backends.postgresql_psycopg2.schema import DatabaseSchemaEditor


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


class DatabaseSchemaEditorIfNotExists(DatabaseSchemaEditor):
    sql_create_index = add_if_not_exists(DatabaseSchemaEditor.sql_create_index)
    sql_create_varchar_index = add_if_not_exists(DatabaseSchemaEditor.sql_create_varchar_index)
    sql_create_text_index = add_if_not_exists(DatabaseSchemaEditor.sql_create_text_index)


class AlterIndexIfNotExists(migrations.AlterIndexTogether):
    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        schema_editor.__class__ = DatabaseSchemaEditorIfNotExists
        try:
            super(AlterIndexIfNotExists, self).database_forwards(
                app_label, schema_editor, from_state, to_state)
        finally:
            schema_editor.__class__ = DatabaseSchemaEditor
