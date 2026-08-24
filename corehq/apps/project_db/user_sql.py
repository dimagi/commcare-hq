"""Translate user-supplied SQL into SQLAlchemy Core expressions.

Only a strict subset of SQL is supported; anything outside it errors
"""
import operator

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

from sqlalchemy import and_, literal, not_, or_, select, union, union_all


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
    if len(statements) != 1:
        raise UnsupportedSQL("this only supports a single statement")

    return _convert_query(statements[0], tables)


def _convert_query(node, tables):
    """Convert a SELECT, or a UNION of them, to a SQLAlchemy ``Selectable``"""
    if isinstance(node, exp.Select):
        return _convert_select(node, tables)
    if isinstance(node, exp.Union):
        # INTERSECT and EXCEPT are other node types, so they are not supported
        this, expression, distinct = _unpack(node, 'this', 'expression', 'distinct')
        left = _convert_query(this, tables)
        right = _convert_query(expression, tables)
        if len(left.c) != len(right.c):
            raise UnsupportedSQL(
                "each side of a UNION must select the same number of columns, "
                f"got {len(left.c)} and {len(right.c)}")
        return union(left, right) if distinct else union_all(left, right)
    raise UnsupportedSQL(f"unsupported statement: {type(node).__name__}")


def _unpack(node, *args):
    """Yield expected args from node, erroring on all others"""
    for key, value in node.args.items():
        if key not in args and value:
            raise UnsupportedSQL(f"unsupported clause in {node} - {key}: {value}")
    return [node.args.get(arg, None) for arg in args]


def _convert_select(node, tables):
    expressions, from_, joins, where, distinct = _unpack(
        node, 'expressions', 'from_', 'joins', 'where', 'distinct')
    if from_ is None:
        raise UnsupportedSQL("a FROM clause is required")
    selectable = _convert_table_ref(from_.this, tables)
    for join in joins or []:
        selectable = _convert_join(join, selectable, tables)
    query = select(_convert_projection(expressions, selectable.c)).select_from(selectable)
    if distinct is not None:
        query = query.distinct(*_convert_distinct_on(distinct, selectable.c))
    if where is not None:
        predicate, = _unpack(where, 'this')
        query = query.where(_convert_predicate(predicate, selectable.c))
    return query


def _convert_distinct_on(node, columns):
    """Resolve the columns of a ``DISTINCT ON``, or none for a plain ``DISTINCT``"""
    on, = _unpack(node, 'on')
    if on is None:
        return []
    on_expressions, = _unpack(on, 'expressions')
    if not on_expressions:
        raise UnsupportedSQL("DISTINCT ON requires at least one column")
    return [_convert_column(e, columns) for e in on_expressions]


def _convert_join(node, selectable, tables):
    """Join another table onto ``selectable``"""
    table_ref, on, side = _unpack(node, 'this', 'on', 'side')
    table = _convert_table_ref(table_ref, tables)
    if table.name in {col.table.name for col in selectable.c}:
        raise UnsupportedSQL(f"table joined more than once: {table.name}")
    predicate = _convert_predicate(on, list(selectable.c) + list(table.c))

    if not side:
        return selectable.join(table, predicate)
    if side == 'LEFT':
        return selectable.outerjoin(table, predicate)
    raise UnsupportedSQL(f"{side} JOIN not supported")


def _convert_projection(expressions, columns):
    """Resolve a SELECT's projection list against the columns in the query"""
    if not expressions:
        raise UnsupportedSQL("a projection is required")
    if all(e == exp.Star() for e in expressions):
        # SELECT * selects every column of every table in the query
        return list(columns)
    return [_convert_projected_column(e, columns) for e in expressions]


def _convert_projected_column(node, columns):
    if isinstance(node, exp.Alias):
        expression, alias = _unpack(node, 'this', 'alias')
        return _convert_column(expression, columns).label(alias.name)
    return _convert_column(node, columns)


def _convert_column(node, columns):
    """Resolve a SQL column reference against the columns in the query"""
    if not isinstance(node, exp.Column):
        raise UnsupportedSQL(f"unsupported expression: {type(node).__name__}")
    identifier, qualifier = _unpack(node, 'this', 'table')
    candidates = [col for col in columns
                  if (qualifier is None or col.table.name == qualifier.name)
                  and col.name == identifier.name]
    if not candidates:
        raise UnsupportedSQL(f"unknown column: {str(node)}")
    if len(candidates) > 1:
        raise UnsupportedSQL(f"ambiguous column: {str(node)}")
    return candidates[0]


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


def _convert_predicate(node, columns):
    """Convert a boolean-valued SQL expression to a ``ColumnElement``"""
    if isinstance(node, exp.Paren):
        inner, = _unpack(node, 'this')
        return _convert_predicate(inner, columns)
    if isinstance(node, exp.Not):
        inner, = _unpack(node, 'this')
        return not_(_convert_predicate(inner, columns))
    if isinstance(node, exp.Is):
        expression, operand, negate = _unpack(node, 'this', 'expression', 'negate')
        if not isinstance(operand, (exp.Null, exp.Boolean)):
            raise UnsupportedSQL("IS only supports NULL, TRUE, and FALSE")
        target, = _unpack(operand, 'this')
        value = _convert_value(expression, columns)
        return value.isnot(target) if negate else value.is_(target)
    if isinstance(node, exp.In):
        value, values = _unpack(node, 'this', 'expressions')
        if not values:
            raise UnsupportedSQL("IN requires at least one value")
        return _convert_value(value, columns).in_(
            [_convert_value(v, columns) for v in values])
    if combine := BOOLEAN_OPS.get(type(node)):
        left, right = _unpack(node, 'this', 'expression')
        return combine(_convert_predicate(left, columns),
                       _convert_predicate(right, columns))
    if compare := COMPARISONS.get(type(node)):
        left, right = _unpack(node, 'this', 'expression')
        return compare(_convert_value(left, columns),
                       _convert_value(right, columns))
    else:
        raise UnsupportedSQL(f"unsupported predicate: {type(node).__name__}")


def _convert_value(node, columns):
    """Convert a SQL value expression to a ``ColumnElement``"""
    if isinstance(node, exp.Literal):
        _unpack(node, 'this', 'is_string')
        return literal(node.to_py())  # Use `literal` to make this a bound parameter
    if isinstance(node, exp.Boolean):
        value, = _unpack(node, 'this')
        return literal(bool(value))
    return _convert_column(node, columns)


def _convert_table_ref(node, tables):
    """Return the table a SQL table reference refers to"""
    if not (isinstance(node, exp.Table) and isinstance(node.this, exp.Identifier)):
        raise UnsupportedSQL(f"expected table, got {str(node)}")
    identifier, = _unpack(node, 'this')
    try:
        return tables[identifier.name]
    except KeyError:
        raise UnsupportedSQL(f"unknown table: {identifier.name}")
