import logging
import re
import time

from django.core.paginator import Paginator
from django.core.paginator import EmptyPage
from django.db import DEFAULT_DB_ALIAS, connections
from django.db.models import Q
from django.db.utils import InterfaceError, OperationalError

logger = logging.getLogger(__name__)

_CHUNK_RETRY_EXCEPTIONS = (OperationalError, InterfaceError)
# Tuned for batch jobs: rides out a DB outage of up to ~31 minutes total.
_CHUNK_RETRY_DELAYS = (1, 2, 4, 8, 15, 30, 60, 2 * 60, 4 * 60, 8 * 60, 15 * 60)


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


def queryset_to_iterator(queryset, model_cls, limit=500, ignore_ordering=False, pagination_key=('pk',)):
    """
    Pull from queryset in chunks. This is suitable for deep pagination, but
    cannot be used with ordered querysets (results will be sorted by the
    ``pagination_key`` fields, by default the pk).

    Retries on transient database connection failures (bounded at ~31
    minutes total) so long-running iterations survive brief outages.
    """
    if queryset.ordered and not ignore_ordering:
        raise AssertionError("queryset_to_iterator does not respect ordering.  "
                             "Pass ignore_ordering=True to continue.")

    queryset = queryset.order_by(*pagination_key)
    last_doc_values = None
    while True:
        if last_doc_values is None:
            chunk_qs = queryset
        else:
            chunk_qs = queryset.filter(_lexicographic_greater_than(pagination_key, last_doc_values))
        chunk = _fetch_chunk_with_retry(chunk_qs, limit, model_cls, last_doc_values)
        if not chunk:
            return
        for doc in chunk:
            yield doc

        last_doc_values = tuple(getattr(doc, field) for field in pagination_key)


def _lexicographic_greater_than(fields, values):
    """Build the tuple comparison ``(a, b, ...) > (va, vb, ...)`` as a Q
    expression, expanding it to ``a > va OR (a = va AND b > vb) OR ...``.
    """
    condition = Q()
    for index, (field, value) in enumerate(zip(fields, values)):
        ties = dict(zip(fields[:index], values[:index]))
        condition |= Q(**ties, **{f"{field}__gt": value})
    return condition


def _fetch_chunk(queryset, limit):
    """Materialize one page of ``queryset``. Patch point for tests."""
    return list(queryset[:limit])


def _fetch_chunk_with_retry(queryset, limit, model_cls, last_doc_values):
    max_attempts = len(_CHUNK_RETRY_DELAYS) + 1
    for attempt in range(max_attempts):
        try:
            return _fetch_chunk(queryset, limit)
        except _CHUNK_RETRY_EXCEPTIONS as exc:
            if attempt == max_attempts - 1:
                logger.error(
                    f"queryset_to_iterator: giving up on {model_cls.__name__} "
                    f"after {attempt + 1} attempts "
                    f"(last_doc_values={last_doc_values!r}): {exc}"
                )
                raise
            delay = _CHUNK_RETRY_DELAYS[attempt]
            logger.warning(
                f"queryset_to_iterator: {type(exc).__name__} fetching "
                f"{model_cls.__name__} chunk (last_doc_values={last_doc_values!r}, "
                f"attempt {attempt + 1}/{max_attempts}); closing connection "
                f"and retrying in {delay}s: {exc}"
            )
            connections[queryset.db].close()
            time.sleep(delay)
