import os
import re

from django.conf import settings
from django.db import connection
from django.db.migrations import RunPython
from django.db.migrations.operations.special import RunSQL
from django.template import Context
from django.template import engines

from corehq.sql_db.routers import allow_migrate


class IndexRenameOperationException(Exception):
    pass


class HqOpMixin(object):
    """
    Hack until we upgrade to Django 1.8 to allow selectively running custom operations
    on different DB's
    """

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        db_alias = schema_editor.connection.alias
        if allow_migrate(db_alias, app_label):
            super(HqOpMixin, self).database_forwards(app_label, schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        db_alias = schema_editor.connection.alias
        if allow_migrate(db_alias, app_label):
            super(HqOpMixin, self).database_backwards(app_label, schema_editor, from_state, to_state)


class HqRunSQL(HqOpMixin, RunSQL):
    pass


class HqRunPython(HqOpMixin, RunPython):
    pass


def noop_migration():
    """
    A migration that does nothing. Used to replace old migrations that are no longer required e.g moved.
    """
    def noop_migration_fn(apps, schema_editor):
        pass

    return RunPython(noop_migration_fn, noop_migration_fn)


class RunSqlLazy(RunSQL):
    """
    Extension of RunSQL that reads the SQL contents from a file "just in time".

    Also supports reading the SQL as a Django template and rendering
    it with the provided template context.
    """

    def __init__(self, sql_template_path, reverse_sql_template_path, template_context=None):
        self.template_context = template_context or {}
        self.rendered_forwards = False
        self.rendered_backwards = False
        super(RunSqlLazy, self).__init__(sql_template_path, reverse_sql_template_path)

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        db_alias = schema_editor.connection.alias
        if allow_migrate(db_alias, app_label):
            if not self.rendered_forwards:
                self.sql = self._render_template(self.sql)
                self.rendered_forwards = True
            super(RunSqlLazy, self).database_forwards(app_label, schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        db_alias = schema_editor.connection.alias
        if allow_migrate(db_alias, app_label):
            if self.reverse_sql:
                if not self.rendered_backwards:
                    self.reverse_sql = self._render_template(self.reverse_sql)
                    self.rendered_backwards = True
            super(RunSqlLazy, self).database_backwards(app_label, schema_editor, from_state, to_state)

    def _render_template(self, path):
        with open(self.sql) as f:
            template_string = f.read()

        template = engines['django'].from_string(template_string)

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

    def get_migration(self, forward_template, reverse_template=Ellipsis, testing_only=False):
        if testing_only and not settings.UNIT_TESTING:
            return noop_migration()

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


def _validate_old_index_name(index_name, table_name):
    if not index_name.startswith(table_name):
        raise IndexRenameOperationException(
            "Expected all indexes on table %s to start with the table name" % table_name
        )


def _validate_identifier(name):
    allowed_chars = re.compile('^[\w\$]+$')
    if not allowed_chars.match(name):
        raise IndexRenameOperationException("Invalid identifier given: %s" % name)


def _rename_table_indexes(from_table, to_table):
    def fcn(apps, schema_editor):
        with connection.cursor() as cursor:
            cursor.execute('SELECT indexname FROM pg_indexes WHERE tablename = %s', [from_table])
            indexes = [row[0] for row in cursor.fetchall()]
            for index_name in indexes:
                _validate_old_index_name(index_name, from_table)
                new_index_name = index_name.replace(from_table, to_table, 1)
                _validate_identifier(index_name)
                _validate_identifier(new_index_name)
                cursor.execute('ALTER INDEX %s RENAME TO %s' % (index_name, new_index_name))

    return fcn


def rename_table_indexes(from_table, to_table):
    """
    Returns a migration operation to rename table indexes to prevent index name
    collision when renaming models. This should be used in conjunction with a
    migrations.RenameModel operation, with this operation being placed right before
    it.

    NOTE: Django unapplies migration operations in LIFO order. In order to
    unapply this rename_table_indexes operation, we would have to unapply the
    rename_table_indexes and rename table operation in FIFO order. So for
    now, not allowing the reverse.
    """
    return HqRunPython(
        _rename_table_indexes(from_table, to_table)
    )
