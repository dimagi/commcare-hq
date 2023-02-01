import json

from django.db import DEFAULT_DB_ALIAS, connection
from django.db import models
from django.db.models.expressions import RawSQL, Ref
from django.db.models.sql.compiler import SQLCompiler
from django.forms import JSONField
from django.test import TestCase

from django_cte import CTEManager, With
from django_cte.raw import raw_cte_sql

from testil import assert_raises, eq

from corehq.util.test_utils import unregistered_django_model

from .. import jsonops as ops


def test_JsonDelete_sql():
    expr = ops.JsonDelete(data_ref, "items", "abc")
    eq(as_sql(expr), "data - ['items', 'abc']")


def test_JsonDelete_illegal_field():
    with assert_raises(ValueError):
        ops.JsonDelete(data_ref, {"nope"})


def test_JsonGet_sql():
    expr = ops.JsonGet(data_ref, "field")
    eq(as_sql(expr), "data->'field'")


def test_JsonSet_sql():
    expr = ops.JsonSet(data_ref, ["items", 0, "abc"], [1, 2, 3])
    eq(as_sql(expr), "jsonb_set(data, ['items', '0', 'abc'], '[1, 2, 3]', true)")


def test_JsonSet_do_not_create_missing():
    expr = ops.JsonSet(data_ref, ["items"], [1, None], create_missing=False)
    eq(as_sql(expr), "jsonb_set(data, ['items'], '[1, null]', false)")


def test_JsonSet_with_expression():
    select = RawSQL("SELECT '{}'::jsonb", [])
    expr = ops.JsonSet(data_ref, ["field"], select)
    eq(as_sql(expr), "jsonb_set(data, ['field'], (SELECT '{}'::jsonb), true)")


def test_nested_operations():
    expr = ops.JsonSet(
        ops.JsonDelete(data_ref, "things"),
        ["items"],
        ops.JsonGet(data_ref, "things"),
    )
    eq(as_sql(expr), "jsonb_set(data - ['things'], ['items'], data->'things', true)")


def test_nested_delete():
    expr = ops.JsonDelete(ops.JsonDelete(data_ref, "one"), "two", "three")
    eq(as_sql(expr), "data - ['one', 'two', 'three']")


class TestJsonOpsEvaluation(TestCase):

    def test_JsonDelete(self):
        value = eval_json_op(ops.JsonDelete(data_ref, "score"))
        self.assertEqual(value, {"things": [1, 2, 3], "other": "value"})

    def test_JsonDelete_fields_with_special_characters(self):
        data = {
            "'": "apostrophe",
            '"': "quotation mark",
            ",": "comma",
            " ": "space",
            "!": "surprise"
        }
        value = eval_json_op(ops.JsonDelete(data_ref, "'", '"', ",", " "), data)
        self.assertEqual(value, {"!": "surprise"})

    def test_JsonSet(self):
        value = eval_json_op(ops.JsonSet(data_ref, ["things", 1], {"b": 2}))
        self.assertEqual(value, {
            "things": [1, {"b": 2}, 3],
            "other": "value",
            "score": 3,
        })

    def test_JsonSet_with_special_characters(self):
        data = {"',": {}}
        value = eval_json_op(ops.JsonSet(data_ref, ["',", ' "'], {"!": 1}), data)
        self.assertEqual(value, {"',": {' "': {"!": 1}}})

    def test_JsonGet(self):
        value = eval_json_op(ops.JsonGet(data_ref, "things"))
        self.assertEqual(value, [1, 2, 3])

    def test_JsonGet_quote(self):
        data = {"'": "apostrophe"}
        value = eval_json_op(ops.JsonGet(data_ref, "'"), data)
        self.assertEqual(value, "apostrophe")

    def test_JsonGet_array_item_by_index(self):
        value = eval_json_op(ops.JsonGet(data_ref, 1), [10, 20, 30])
        self.assertEqual(value, 20)

    def test_JsonGet_backslash(self):
        data = {"\\": "backslash"}
        value = eval_json_op(ops.JsonGet(data_ref, "\\"), data)
        self.assertEqual(value, "backslash")

    def test_JsonGet_comma_quotation_mark(self):
        data = {',"': "comma quotation mark"}
        value = eval_json_op(ops.JsonGet(data_ref, ',"'), data)
        self.assertEqual(value, "comma quotation mark")

    def test_nested_operations(self):
        value = eval_json_op(ops.JsonSet(
            ops.JsonDelete(data_ref, "things"),
            ["items"],
            ops.JsonGet(data_ref, "things"),
        ))
        self.assertEqual(value, {
            "items": [1, 2, 3],
            "other": "value",
            "score": 3,
        })


class _UnquotedRef(Ref):

    def as_sql(self, compiler, connection):
        return self.refs, []


data_ref = _UnquotedRef("data", None)


def as_sql(expression):
    compiler = SQLCompiler(None, connection, DEFAULT_DB_ALIAS)
    sql, params = compiler.compile(expression)
    return sql % tuple(repr(p) for p in params)


def eval_json_op(expression, data=None):
    # raw CTE is a hack to evaluate a query without an existing model
    data = data or {"things": [1, 2, 3], "other": "value", "score": 3}
    cte_sql = "SELECT %s::jsonb AS data"
    data_cte = raw_cte_sql(cte_sql, [json.dumps(data)], {"data": JSONField()})
    data_cte.query.model = _JsonModel
    data_cte.query.default_cols = []
    data_cte.query.annotations = {}
    data_cte.query.values_select = []
    data_cte.query.annotation_select_mask = None
    cte = With(data_cte)
    qs = (
        cte.queryset().with_cte(cte)
        .annotate(val=expression)
        .values_list("val", flat=True)
    )
    print(qs.query)
    value, = qs
    return value


@unregistered_django_model
class _JsonModel(models.Model):
    objects = CTEManager()
