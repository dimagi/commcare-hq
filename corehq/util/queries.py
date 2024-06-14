import re

from django.core.paginator import Paginator
from django.core.paginator import EmptyPage
from django.db import DEFAULT_DB_ALIAS


def fast_distinct(model_cls, column, using=DEFAULT_DB_ALIAS):
    """
    Use a loose indexscan http://wiki.postgresql.org/wiki/Loose_indexscan
    to get all distinct values for a given column

    Functionally equivalent to
    model_cls.objects.using(using).distinct(column).values_list(column, flat=True)
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

    return [value for value, in _execute(command, using=using)]


def fast_distinct_in_domain(model_cls, column, domain, using=DEFAULT_DB_ALIAS):
    """
    Use a loose indexscan http://wiki.postgresql.org/wiki/Loose_indexscan
    to get all distinct values for a given column in a certain domain

    Functionally equivalent to

        model_cls.objects.using(using).filter(domain=domain).values(column) \
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
    SELECT NULL WHERE EXISTS(SELECT * FROM {table} WHERE {column} IS NULL AND {filter_column} = %(filter_value)s);
    """.format(
        column=_assert_super_safe(column),
        table=_assert_super_safe(table),
        filter_column=_assert_super_safe('domain')
    )
    return [value for value, in _execute(command, {'filter_value': domain}, using=using)]


def _get_table_from_model(model_cls):
    return model_cls._meta.db_table


def _assert_field_in_model(model_cls, column):
    assert column in [field.name for field in model_cls._meta.fields]


def _assert_super_safe(word):
    assert re.match(r'^\w+$', word)
    return word


def _execute(command, params=None, using=DEFAULT_DB_ALIAS):
    from django.db import connections
    connection = connections[using]
    with connection.cursor() as cursor:
        if params is None:
            cursor.execute(command)
        else:
            cursor.execute(command, params)
        for row in cursor.fetchall():
            yield row


def paginated_queryset(queryset, chunk_size):
    # Paginate a large queryset into multiple smaller queries
    paginator = Paginator(queryset, chunk_size)
    page = 0
    while True:
        page += 1
        try:
            for obj in paginator.page(page):
                yield obj
        except EmptyPage:
            return


def queryset_to_iterator(queryset, model_cls, limit=500, ignore_ordering=False, paginate_by={}):
    """
    Pull from queryset in chunks. This is suitable for deep pagination, but
    cannot be used with ordered querysets (results will be sorted by pk).
    :param paginate_by: optional dictionary of {field: conditional,} to specify what fields pagination should key
    off of and how. This means that order of fields matters, since this prioritizes how sorting will be done.
    """
    if queryset.ordered and not ignore_ordering:
        raise AssertionError("queryset_to_iterator does not respect ordering.  "
                             "Pass ignore_ordering=True to continue.")

    if not paginate_by:
        pk_field = model_cls._meta.pk.name
        paginate_by = {pk_field: "gt"}

    queryset = queryset.order_by(*list(paginate_by.keys()))
    docs = queryset[:limit]
    while docs:
        yield from docs

        if len(docs) < limit:
            break

        last_doc = docs[len(docs) - 1]
        last_doc_values = {}
        for field, condition in paginate_by.items():
            key = f"{field}__{condition}"
            last_doc_values[key] = getattr(last_doc, field)

        docs = queryset.filter(**last_doc_values)[:limit]
