import os

from django.db import migrations


def noop_migration_fn(apps, schema_editor):
    pass


def noop_migration():
    """
    A migration that does nothing. Used to replace old migrations that are no longer required e.g moved.
    """
    return migrations.RunPython(noop_migration_fn, noop_migration_fn)


class RunSQLLazy(migrations.RunSQL):
    """
    Extension of RunSQL that reads the SQL contents from a file "just in time".
    """
    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        self.sql = self._get_file_content(self.sql)
        super(RunSQLLazy, self).database_forwards(app_label, schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        if self.reverse_sql:
            self.reverse_sql = self._get_file_content(self.reverse_sql)
        super(RunSQLLazy, self).database_backwards(app_label, schema_editor, from_state, to_state)

    def _get_file_content(self, path):
        with open(self.sql) as f:
            return f.read()


class RawSQLMigration(object):
    def __init__(self, base_path_tuple):
        self.base_path = os.path.join(*base_path_tuple)

    def get_migration(self, forward_file, reverse_file=Ellipsis):
        forward_path = os.path.join(self.base_path, forward_file)

        if reverse_file is Ellipsis:
            # reverse could be None to make the migration non-reversible
            reverse_file = 'SELECT 1'  # noop reverse

        reverse_path = None
        if reverse_file:
            reverse_path = os.path.join(self.base_path, reverse_file)

        return RunSQLLazy(
            forward_path,
            reverse_path
        )
