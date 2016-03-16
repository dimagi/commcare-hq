import re


def fast_distinct(model_cls, column):
    """
    Use a loose indexscan http://wiki.postgresql.org/wiki/Loose_indexscan
    to get all distinct values for a given column

    Functionally equivalent to
    model_cls.distinct(column).values_list(column, flat=True)
    """
    table = _get_table_from_model(model_cls)
    _assert_field_in_model(model_cls, column)
    command = """
    WITH RECURSIVE t AS (
        SELECT min({column}) AS col FROM {table}
        UNION ALL
        SELECT (SELECT min({column}) FROM {table} WHERE {column} > t.col)
        FROM t WHERE t.col IS NOT NULL
    )
    SELECT col FROM t WHERE col IS NOT NULL
    UNION ALL
    SELECT NULL WHERE EXISTS(SELECT * FROM {table} WHERE {column} IS NULL);
    """.format(column=_assert_super_safe(column), table=_assert_super_safe(table))

    return [value for value, in _execute(command)]


def fast_distinct_in_domain(model_cls, column, domain):
    """
    Use a loose indexscan http://wiki.postgresql.org/wiki/Loose_indexscan
    to get all distinct values for a given column in a certain domain

    Functionally equivalent to

        model_cls.objects.filter(domain=domain).values(column) \
            .distinct().values_list(column, flat=True)
    """
    table = _get_table_from_model(model_cls)
    _assert_field_in_model(model_cls, column)

    command = """
    WITH RECURSIVE t AS (
        SELECT min({column}) AS col FROM {table} WHERE {filter_column} = %(filter_value)s
        UNION ALL
        SELECT (SELECT min({column}) FROM {table} WHERE {column} > t.col AND {filter_column} = %(filter_value)s)
        FROM t WHERE t.col IS NOT NULL
    )
    SELECT col FROM t WHERE col IS NOT NULL
    UNION ALL
    SELECT NULL WHERE EXISTS(SELECT * FROM {table} WHERE {column} IS NULL);
    """.format(column=_assert_super_safe(column), table=_assert_super_safe(table),
               filter_column=_assert_super_safe('domain'))
    return [value for value, in _execute(command, {'filter_value': domain})]


def _get_table_from_model(model_cls):
    return model_cls._meta.db_table


def _assert_field_in_model(model_cls, column):
    assert column in [field.name for field in model_cls._meta.fields]


def _assert_super_safe(word):
    assert re.match(r'^\w+$', word)
    return word


def _execute(command, params=None):
    from django.db import connection
    with connection.cursor() as cursor:
        if params is None:
            cursor.execute(command)
        else:
            cursor.execute(command, params)
        for row in cursor.fetchall():
            yield row
