"""Translate user-supplied SQL into SQLAlchemy Core expressions.

Only a strict subset of SQL is supported; anything outside it errors
"""
import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

from sqlalchemy import select


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
    expressions, from_ = _unpack(node, 'expressions', 'from_')
    if not all(e == exp.Star() for e in expressions):
        raise UnsupportedSQL("only 'SELECT *' is supported")
    if from_ is None:
        raise UnsupportedSQL("a FROM clause is required")
    return select([_convert_table_ref(from_.this, tables)])


def _convert_table_ref(node, tables):
    """Convert a SQL table reference to a SQLAlchemy ``Selectable``"""
    if not (isinstance(node, exp.Table) and isinstance(node.this, exp.Identifier)):
        raise UnsupportedSQL(f"expected table, got {str(node)}")
    identifier, = _unpack(node, 'this')
    try:
        return tables[identifier.name]
    except KeyError:
        raise UnsupportedSQL(f"unknown table: {identifier.name}")
