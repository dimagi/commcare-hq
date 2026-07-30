"""Translate user-supplied SQL into SQLAlchemy Core expressions.

Only a strict subset of SQL is supported; anything outside it errors
"""
import operator

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

from sqlalchemy import and_, literal, not_, or_, select


class UnsupportedSQL(Exception):
    """Raised when the input uses SQL that the translator does not support."""


def translate(sql, tables):
    """Translate a SQL string into a SQLAlchemy Core selectable.

    :param sql: the user-supplied SQL statement
    :param tables: mapping of table name to SQLAlchemy ``Table``
    """
    try:
        statements = sqlglot.parse(sql, read='postgres')
    except SqlglotError:
        raise UnsupportedSQL("could not parse SQL")
    if len(statements) != 1 or not isinstance(statements[0], exp.Select):
        raise UnsupportedSQL("this only supports a single SELECT statement")

    return _convert_select(statements[0], tables)


def _unpack(node, *args):
    """Yield expected args from node, erroring on all others"""
    for key, value in node.args.items():
        if key not in args and value:
            raise UnsupportedSQL(f"unsupported clause in {node} - {key}: {value}")
    return [node.args.get(arg, None) for arg in args]


def _convert_select(node, tables):
    expressions, from_, where = _unpack(node, 'expressions', 'from_', 'where')
    if from_ is None:
        raise UnsupportedSQL("a FROM clause is required")
    table = _convert_table_ref(from_.this, tables)
    query = select(_convert_projection(expressions, table))
    if where is not None:
        predicate, = _unpack(where, 'this')
        query = query.where(_convert_predicate(predicate, table))
    return query


def _convert_projection(expressions, table):
    """Resolve a SELECT's projection list against ``table``"""
    if not expressions:
        raise UnsupportedSQL("a projection is required")
    if all(e == exp.Star() for e in expressions):
        return [table]  # SELECT * selects the whole table
    return [_convert_column(e, table) for e in expressions]


def _convert_column(node, table):
    if not isinstance(node, exp.Column):
        raise UnsupportedSQL(f"unsupported expression: {type(node).__name__}")
    identifier, = _unpack(node, 'this')
    try:
        return table.c[identifier.name]
    except KeyError:
        raise UnsupportedSQL(f"unknown column: {identifier.name}")


BOOLEAN_OPS = {
    exp.And: and_,
    exp.Or: or_,
}

COMPARISONS = {
    exp.EQ: operator.eq,
    exp.NEQ: operator.ne,
    exp.GT: operator.gt,
    exp.GTE: operator.ge,
    exp.LT: operator.lt,
    exp.LTE: operator.le,
}


def _convert_predicate(node, table):
    """Convert a boolean-valued SQL expression to a ``ColumnElement``"""
    if isinstance(node, exp.Paren):
        inner, = _unpack(node, 'this')
        return _convert_predicate(inner, table)
    if isinstance(node, exp.Not):
        inner, = _unpack(node, 'this')
        return not_(_convert_predicate(inner, table))
    if isinstance(node, exp.In):
        value, values = _unpack(node, 'this', 'expressions')
        if not values:
            raise UnsupportedSQL("IN requires at least one value")
        return _convert_value(value, table).in_(
            [_convert_value(v, table) for v in values])
    if combine := BOOLEAN_OPS.get(type(node)):
        left, right = _unpack(node, 'this', 'expression')
        return combine(_convert_predicate(left, table),
                       _convert_predicate(right, table))
    if compare := COMPARISONS.get(type(node)):
        left, right = _unpack(node, 'this', 'expression')
        return compare(_convert_value(left, table),
                       _convert_value(right, table))
    else:
        raise UnsupportedSQL(f"unsupported predicate: {type(node).__name__}")


def _convert_value(node, table):
    """Convert a SQL value expression to a ``ColumnElement``"""
    if isinstance(node, exp.Literal):
        _unpack(node, 'this', 'is_string')
        return literal(node.to_py())  # Use `literal` to make this a bound parameter
    if isinstance(node, exp.Boolean):
        value, = _unpack(node, 'this')
        return literal(bool(value))
    return _convert_column(node, table)


def _convert_table_ref(node, tables):
    """Convert a SQL table reference to a SQLAlchemy ``Selectable``"""
    if not (isinstance(node, exp.Table) and isinstance(node.this, exp.Identifier)):
        raise UnsupportedSQL(f"expected table, got {str(node)}")
    identifier, = _unpack(node, 'this')
    try:
        return tables[identifier.name]
    except KeyError:
        raise UnsupportedSQL(f"unknown table: {identifier.name}")
