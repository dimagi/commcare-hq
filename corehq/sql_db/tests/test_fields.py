from django.db import connection
from django.db import models
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


def schema_editor():
    return DatabaseSchemaEditor(connection, collect_sql=True, atomic=False)


def assert_no_pattern_ops_index(editor):
    statements = editor.collected_sql + editor.deferred_sql
    assert statements, "expected at least one SQL statement"
    print("\n".join(str(s) for s in statements))
    for sql in statements:
        assert "_pattern_ops" not in str(sql), repr(sql)
