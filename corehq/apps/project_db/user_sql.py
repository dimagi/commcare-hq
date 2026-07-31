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
    expressions, from_, joins, where = _unpack(node, 'expressions', 'from_', 'joins', 'where')
    if from_ is None:
        raise UnsupportedSQL("a FROM clause is required")
    selectable = _convert_table_ref(from_.this, tables)
    # Tables available to resolve column references against, by name
    sources = {selectable.name: selectable}
    for join in joins or []:
        selectable = _convert_join(join, selectable, sources, tables)
    query = select(_convert_projection(expressions, sources)).select_from(selectable)
    if where is not None:
        predicate, = _unpack(where, 'this')
        query = query.where(_convert_predicate(predicate, sources))
    return query


def _convert_join(node, selectable, sources, tables):
    """Join another table onto ``selectable``, adding it to ``sources``"""
    table_ref, on, side = _unpack(node, 'this', 'on', 'side')

    table = _convert_table_ref(table_ref, tables)
    if table.name in sources:
        raise UnsupportedSQL(f"table joined more than once: {table.name}")
    sources[table.name] = table
    predicate = _convert_predicate(on, sources)

    if not side:
        return selectable.join(table, predicate)
    if side == 'LEFT':
        return selectable.outerjoin(table, predicate)
    raise UnsupportedSQL(f"{side} JOIN not supported")


def _convert_projection(expressions, sources):
    """Resolve a SELECT's projection list against ``sources``"""
    if not expressions:
        raise UnsupportedSQL("a projection is required")
    if all(e == exp.Star() for e in expressions):
        # SELECT * selects every column of every table in the query
        return [col for table in sources.values() for col in table.c]
    return [_convert_column(e, sources) for e in expressions]


def _convert_column(node, sources):
    if not isinstance(node, exp.Column):
        raise UnsupportedSQL(f"unsupported expression: {type(node).__name__}")
    identifier, qualifier = _unpack(node, 'this', 'table')
    name = identifier.name
    if qualifier is None:
        candidates = [table for table in sources.values() if name in table.c]
    elif qualifier.name in sources:
        table = sources[qualifier.name]
        candidates = [table] if name in table.c else []
    else:
        raise UnsupportedSQL(f"unknown table: {qualifier.name}")
    if not candidates:
        raise UnsupportedSQL(f"unknown column: {name}")
    if len(candidates) > 1:
        raise UnsupportedSQL(f"ambiguous column: {name}")
    return candidates[0].c[name]


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


def _convert_predicate(node, sources):
    """Convert a boolean-valued SQL expression to a ``ColumnElement``"""
    if isinstance(node, exp.Paren):
        inner, = _unpack(node, 'this')
        return _convert_predicate(inner, sources)
    if isinstance(node, exp.Not):
        inner, = _unpack(node, 'this')
        return not_(_convert_predicate(inner, sources))
    if isinstance(node, exp.Is):
        expression, operand, negate = _unpack(node, 'this', 'expression', 'negate')
        if not isinstance(operand, (exp.Null, exp.Boolean)):
            raise UnsupportedSQL("IS only supports NULL, TRUE, and FALSE")
        target, = _unpack(operand, 'this')
        value = _convert_value(expression, sources)
        return value.isnot(target) if negate else value.is_(target)
    if isinstance(node, exp.In):
        value, values = _unpack(node, 'this', 'expressions')
        if not values:
            raise UnsupportedSQL("IN requires at least one value")
        return _convert_value(value, sources).in_(
            [_convert_value(v, sources) for v in values])
    if combine := BOOLEAN_OPS.get(type(node)):
        left, right = _unpack(node, 'this', 'expression')
        return combine(_convert_predicate(left, sources),
                       _convert_predicate(right, sources))
    if compare := COMPARISONS.get(type(node)):
        left, right = _unpack(node, 'this', 'expression')
        return compare(_convert_value(left, sources),
                       _convert_value(right, sources))
    else:
        raise UnsupportedSQL(f"unsupported predicate: {type(node).__name__}")


def _convert_value(node, sources):
    """Convert a SQL value expression to a ``ColumnElement``"""
    if isinstance(node, exp.Literal):
        _unpack(node, 'this', 'is_string')
        return literal(node.to_py())  # Use `literal` to make this a bound parameter
    if isinstance(node, exp.Boolean):
        value, = _unpack(node, 'this')
        return literal(bool(value))
    return _convert_column(node, sources)


def _convert_table_ref(node, tables):
    """Convert a SQL table reference to a SQLAlchemy ``Selectable``"""
    if not (isinstance(node, exp.Table) and isinstance(node.this, exp.Identifier)):
        raise UnsupportedSQL(f"expected table, got {str(node)}")
    identifier, = _unpack(node, 'this')
    try:
        return tables[identifier.name]
    except KeyError:
        raise UnsupportedSQL(f"unknown table: {identifier.name}")
