from collections import namedtuple


def fetchall_as_namedtuple(cursor):
    "Return all rows from a cursor as a namedtuple"
    Result = _namedtuple_from_cursor(cursor)
    return [Result(*row) for row in cursor.fetchall()]


def fetchone_as_namedtuple(cursor):
    "Return one row from a cursor as a namedtuple"
    Result = _namedtuple_from_cursor(cursor)
    row = cursor.fetchone()
    return Result(*row)


def _namedtuple_from_cursor(cursor):
    desc = cursor.description
    return namedtuple('Result', [col[0] for col in desc])
