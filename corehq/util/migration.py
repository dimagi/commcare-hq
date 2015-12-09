import os

from django.db import migrations
from django.template import Context
from django.template.loader import get_template_from_string


def noop_migration_fn(apps, schema_editor):
    pass


def noop_migration():
    """
    A migration that does nothing. Used to replace old migrations that are no longer required e.g moved.
    """
    return migrations.RunPython(noop_migration_fn, noop_migration_fn)


class RunSqlLazy(migrations.RunSQL):
    """
    Extension of RunSQL that reads the SQL contents from a file "just in time".

    Also supports reading the SQL as a Django template and rendering
    it with the provided template context.
    """
    def __init__(self, sql_template_path, reverse_sql_template_path, template_context=None):
        self.template_context = template_context or {}
        super(RunSqlLazy, self).__init__(sql_template_path, reverse_sql_template_path)

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        self.sql = self._render_template(self.sql)
        super(RunSqlLazy, self).database_forwards(app_label, schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        if self.reverse_sql:
            self.reverse_sql = self._render_template(self.reverse_sql)
        super(RunSqlLazy, self).database_backwards(app_label, schema_editor, from_state, to_state)

    def _render_template(self, path):
        with open(self.sql) as f:
            template_string = f.read()

        template = get_template_from_string(template_string)
        return template.render(Context(self.template_context))


class RawSQLMigration(object):
    """
    Helper class for running raw SQL migrations.
    Usage:

        migrator = RawSQLMigration(('base', 'path'), {'variable': 'value'})
        migrator.get_migration('sql_template.sql')
    """
    def __init__(self, base_path_tuple, template_context=None):
        self.template_context = template_context
        self.base_path = os.path.join(*base_path_tuple)

    def get_migration(self, forward_template, reverse_template=Ellipsis):
        forward_path = os.path.join(self.base_path, forward_template)

        if reverse_template is Ellipsis:
            # reverse could be None to make the migration non-reversible
            reverse_template = 'SELECT 1'  # noop reverse

        reverse_path = None
        if reverse_template:
            reverse_path = os.path.join(self.base_path, reverse_template)

        return RunSqlLazy(
            forward_path,
            reverse_path,
            self.template_context
        )
