"""Translate user-supplied SQL into SQLAlchemy Core expressions.

Only a strict subset of SQL is supported; anything outside it errors
"""
import operator
import re
import time
from collections import namedtuple
from functools import cached_property

import sqlglot
from sqlalchemy import (
    and_,
    bindparam,
    not_,
    nullsfirst,
    nullslast,
    or_,
    select,
    union,
    union_all,
)
from sqlalchemy.dialects import postgresql
from sqlglot import exp
from sqlglot.errors import SqlglotError

from corehq.apps.project_db.table_ddl import (
    get_domain_tables,
    get_project_db_engine,
)


class UserSQLValidationError(Exception):
    def __init__(self, msg):
        self.msg = msg


class UnsupportedSQL(UserSQLValidationError):
    """Raised when the input uses SQL that the translator does not support."""


class BadParameters(UserSQLValidationError):
    """The parameters don't match the query"""


LITERAL_PARAM_PREFIX = 'hq_param'  # Our reserved namespace for parameters

# A query parameter's name is interpolated into the compiled SQL, so it is
# restricted to characters that cannot close the placeholder and inject SQL.
PARAM_NAME = re.compile(r'[A-Za-z_][A-Za-z0-9_]*\Z')

MAX_PAREN_DEPTH = 20

NESTED_TOO_DEEPLY = "SQL is nested too deeply"


def _bind(value):
    """Bind a value as a uniquely named parameter"""
    return bindparam(LITERAL_PARAM_PREFIX, value, unique=True)


QueryInfo = namedtuple('QueryInfo', 'translated_sql bound_literals parameters')
QueryResult = namedtuple('QueryResult', 'columns rows duration')


class UserSQL:
    def __init__(self, domain, raw_sql):
        self.domain = domain
        self.raw_sql = raw_sql

    @cached_property
    def query(self):
        return translate(self.raw_sql, get_domain_tables(self.domain))

    @cached_property
    def _compiled(self):
        return self.query.compile(dialect=postgresql.dialect(paramstyle='named'))

    def get_info(self):
        return QueryInfo(
            translated_sql=sqlglot.transpile(
                str(self._compiled), read='postgres', write='postgres', pretty=True
            )[0],
            bound_literals={
                name: value for name, value in self._compiled.params.items()
                if name not in self.parameters
            },
            parameters=self.parameters,
        )

    @property
    def parameters(self):
        """Return the parameters a translated query leaves for the caller to supply"""
        return [name for name, bind in self._compiled.binds.items() if bind.required]

    def run(self, parameter_values, max_rows):
        params = self._clean_parameters(parameter_values)
        with get_project_db_engine().connect() as conn:
            start = time.perf_counter()
            result = conn.execute(self.query, params)
            rows = result.fetchmany(max_rows)
            return QueryResult(
                columns=list(result.keys()),
                rows=rows,
                duration=time.perf_counter() - start,
            )

    def _clean_parameters(self, raw_parameters):
        if set(raw_parameters) != set(self.parameters):
            raise BadParameters(f"Expected params {set(self.parameters)}, got {set(raw_parameters)}")
        return {name: raw_parameters[name] for name in self.parameters}


def translate(sql, tables):
    """Translate a SQL string into a SQLAlchemy Core selectable.

    :param sql: the user-supplied SQL statement
    :param tables: mapping of table name to SQLAlchemy ``Table``
    """
    # sqlglot's parser recurses about 20 stack frames per level of parentheses,
    # so deeply nested input exhausts the stack
    _check_paren_depth(sql)
    try:
        statements = sqlglot.parse(sql, read='postgres')
    except SqlglotError:
        raise UnsupportedSQL("could not parse SQL")
    if len(statements) != 1:
        raise UnsupportedSQL("this only supports a single statement")

    return _convert_query(statements[0], tables)


def _check_paren_depth(sql):
    """Reject SQL whose parentheses nest deeper than the parser can handle"""
    depth = 0
    for char in sql:
        if char == '(':
            depth += 1
            if depth > MAX_PAREN_DEPTH:
                raise UnsupportedSQL(NESTED_TOO_DEEPLY)
        elif char == ')':
            depth -= 1


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
    expressions, from_, joins, where, distinct, order = _unpack(
        node, 'expressions', 'from_', 'joins', 'where', 'distinct', 'order')
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
    if order is not None:
        query = query.order_by(*_convert_order(order, selectable.c))
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


def _convert_order(node, columns):
    """Convert an ORDER BY clause to a list of sort keys"""
    order_expressions, = _unpack(node, 'expressions')
    return [_convert_sort_key(e, columns) for e in order_expressions]


def _convert_sort_key(node, columns):
    expression, desc, nulls_first = _unpack(node, 'this', 'desc', 'nulls_first')
    col = _convert_column(expression, columns)
    sort_key = col.desc() if desc else col.asc()
    return nullsfirst(sort_key) if nulls_first else nullslast(sort_key)


def _convert_join(node, selectable, tables):
    """Join another table onto ``selectable``"""
    table_ref, on, side = _unpack(node, 'this', 'on', 'side')
    table = _convert_table_ref(table_ref, tables)
    if table.name in {col.table.name for col in selectable.c}:
        raise UnsupportedSQL(f"table name used more than once: {table.name}")
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

ARRAY_OPS = {
    exp.ArrayContainsAll: '@>',
    exp.ArrayContainedBy: '<@',
    exp.ArrayOverlaps: '&&',
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
        value, values, field = _unpack(node, 'this', 'expressions', 'field')
        operand = _convert_value(value, columns)
        if field is not None:
            if not isinstance(field, exp.Placeholder):
                raise UnsupportedSQL(f"unsupported IN expression: {str(field)}")
            return operand.in_(_convert_placeholder(field, expanding=True))
        if not values:
            raise UnsupportedSQL("IN requires at least one value")
        return operand.in_([_convert_value(v, columns) for v in values])
    if combine := BOOLEAN_OPS.get(type(node)):
        left, right = _unpack(node, 'this', 'expression')
        return combine(_convert_predicate(left, columns),
                       _convert_predicate(right, columns))
    if array_op := ARRAY_OPS.get(type(node)):
        left, right = _unpack(node, 'this', 'expression')
        contains = _convert_value(left, columns).bool_op(array_op)
        return contains(_convert_value(right, columns))
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
        return _bind(node.to_py())  # Bind it so the value never reaches the SQL
    if isinstance(node, exp.Boolean):
        value, = _unpack(node, 'this')
        return _bind(bool(value))
    if isinstance(node, exp.Array):
        return _convert_array(node)
    if isinstance(node, exp.Placeholder):
        return _convert_placeholder(node)
    return _convert_column(node, columns)


def _convert_placeholder(node, expanding=False):
    """Convert a ``:name`` placeholder to a parameter for the caller to bind"""
    name, = _unpack(node, 'this')
    if not isinstance(name, str) or not PARAM_NAME.match(name):
        raise UnsupportedSQL("query parameters must be written as `:name`")
    if name.startswith(LITERAL_PARAM_PREFIX):
        raise UnsupportedSQL(f"query parameter names may not begin with '{LITERAL_PARAM_PREFIX}'")
    return bindparam(name, expanding=expanding)


def _convert_array(node):
    """Convert an ``ARRAY[...]`` literal into a single bound parameter"""
    elements, = _unpack(node, 'expressions')
    for element in elements:
        if not isinstance(element, exp.Literal):
            raise UnsupportedSQL(f"array elements must be literals: {str(element)}")
        _unpack(element, 'this', 'is_string')
    return _bind([element.to_py() for element in elements])


def _convert_table_ref(node, tables):
    """Return the table a SQL table reference refers to"""
    if not (isinstance(node, exp.Table) and isinstance(node.this, exp.Identifier)):
        raise UnsupportedSQL(f"expected table, got {str(node)}")
    identifier, alias = _unpack(node, 'this', 'alias')
    try:
        selectable = tables[identifier.name]
    except KeyError:
        raise UnsupportedSQL(f"unknown table: {identifier.name}")
    if alias is not None:
        alias_identifier, = _unpack(alias, 'this')
        return selectable.alias(alias_identifier.name)
    return selectable
