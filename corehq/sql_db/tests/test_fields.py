from contextlib import contextmanager
from unittest.mock import patch

from django.db import connection, models
from django.db.backends.postgresql.schema import DatabaseSchemaEditor

from corehq.util.test_utils import unregistered_django_model

from ..fields import CharIdField


def test_CharIdField_without_indexes():
    @unregistered_django_model
    class Test(models.Model):
        some_id = CharIdField()
    field = {f.name: f for f in Test._meta.fields}["some_id"]
    with schema_editor() as editor:
        editor.add_field(Test, field)
        assert_no_pattern_ops_index(editor)


def test_CharIdField_primary_key():
    @unregistered_django_model
    class Test(models.Model):
        id = CharIdField(primary_key=True)
    field = {f.name: f for f in Test._meta.fields}["id"]
    assert field.unique
    with schema_editor() as editor:
        editor.add_field(Test, field)
        assert_no_pattern_ops_index(editor)


def test_CharIdField_with_index():
    @unregistered_django_model
    class Test(models.Model):
        domain = CharIdField(db_index=True, max_length=25)
    field = {f.name: f for f in Test._meta.fields}["domain"]
    with schema_editor() as editor:
        editor.add_field(Test, field)
        assert_no_pattern_ops_index(editor)


def test_CharField_has_pattern_ops_index():
    # Confirm that the testing technique used by the tests above produces a
    # varchar_pattern_ops index with CharField instead of CharIdField.
    @unregistered_django_model
    class Test(models.Model):
        domain = models.CharField(db_index=True, max_length=25)
    field = {f.name: f for f in Test._meta.fields}["domain"]
    with schema_editor() as editor:
        editor.add_field(Test, field)
        statements = editor.collected_sql + editor.deferred_sql
        assert has_pattern_ops_index(statements), statements


@contextmanager
def schema_editor():
    def capture_sql_output(sql, params=None):
        editor.collected_sql.append(sql)
    schema = DatabaseSchemaEditor(connection, collect_sql=True, atomic=False)
    with patch.object(schema, 'execute', capture_sql_output), schema as editor:
        yield editor


def assert_no_pattern_ops_index(editor):
    statements = editor.collected_sql + editor.deferred_sql
    assert statements, "expected at least one SQL statement"
    assert not has_pattern_ops_index(statements), \
        "\n".join(str(s) for s in statements)


def has_pattern_ops_index(statements):
    return any("_pattern_ops" in str(sql) for sql in statements)
