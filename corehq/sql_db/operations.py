from __future__ import absolute_import, unicode_literals

import os
import re
from io import open

from django.conf import settings
from django.db import connection, router
from django.db.migrations import RunPython, RunSQL
from django.template import engines

import attr

from corehq.util.django_migrations import noop_migration

NOOP = object()


class IndexRenameOperationException(Exception):
    pass


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
        if router.allow_migrate(schema_editor.connection.alias, app_label, **self.hints):
            if not self.rendered_forwards:
                self.sql = self._render_template(self.sql)
                self.rendered_forwards = True
            super(RunSqlLazy, self).database_forwards(app_label, schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        if router.allow_migrate(schema_editor.connection.alias, app_label, **self.hints):
            if self.reverse_sql:
                if not self.rendered_backwards:
                    self.reverse_sql = self._render_template(self.reverse_sql)
                    self.rendered_backwards = True
            super(RunSqlLazy, self).database_backwards(app_label, schema_editor, from_state, to_state)

    def _render_template(self, path):
        if path is NOOP:
            return "SELECT 1"

        if isinstance(path, SQL):
            template_string = path.value
        else:
            with open(path, encoding='utf-8') as f:
                template_string = f.read()

        template = engines['django'].from_string(template_string)

        return template.render(self.template_context)


@attr.s
class SQL(object):
    """Marker class for SQL template strings"""
    value = attr.ib()


class RawSQLMigration(object):
    """
    Helper class for running raw SQL migrations.
    Usage:

        migrator = RawSQLMigration(('base', 'path'), {'variable': 'value'})
        migrator.get_migration('sql_template.sql')

    The reverse migration will be a no-op by default. To make a
    non-reversible migration, set the reverse template to None:

        migrator.get_migration('sql_template.sql', None)  # non-reversible

    Raw SQL templates (instead of a template names) can be passed to
    `get_migration`:

        migrator.get_migration(
            'get_something.sql',
            SQL("DROP FUNCTION get_something(TEXT);"),
        )
    """

    def __init__(self, base_path_tuple, template_context=None):
        self.template_context = template_context
        self.base_path = os.path.join(*base_path_tuple)

    def get_migration(self, forward_template, reverse_template=NOOP, testing_only=False):
        if testing_only and not settings.UNIT_TESTING:
            return noop_migration()

        if isinstance(forward_template, SQL):
            forward_path = forward_template
        else:
            forward_path = os.path.join(self.base_path, forward_template)

        if reverse_template is NOOP:
            reverse_path = NOOP
        elif reverse_template is None:
            reverse_path = None  # make the migration non-reversible
        elif isinstance(reverse_template, SQL):
            reverse_path = reverse_template
        else:
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
    allowed_chars = re.compile(r'^[\w\$]+$')
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
    return RunPython(
        _rename_table_indexes(from_table, to_table)
    )
