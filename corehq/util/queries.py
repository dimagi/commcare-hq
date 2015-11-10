def fast_distinct(model_cls, column):
    """
    Use a loose indexscan http://wiki.postgresql.org/wiki/Loose_indexscan
    to get all distinct values for a given column

    Functionally equivalent to
    model_cls.distinct(column).values_list(column, flat=True)
    """
    table = model_cls._meta.db_table
    assert column in [field.name for field in model_cls._meta.fields]
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
    """.format(column=column, table=table)
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute(command)
        result = []
        for value, in cursor.fetchall():
            result.append(value)
    return result
