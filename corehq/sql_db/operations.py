from django.db.migrations import RunPython
from django.db.migrations.operations.special import RunSQL

from corehq.sql_db.routers import allow_migrate


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
