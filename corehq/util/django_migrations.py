from django.db import migrations
from django.db.backends.postgresql_psycopg2.schema import DatabaseSchemaEditor


def add_if_not_exists(string):
    return string.replace('CREATE INDEX', 'CREATE INDEX IF NOT EXISTS')


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
