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


def queryset_to_iterator(queryset, model_cls, limit=500, ignore_ordering=False,
                         pagination_key=('pk',), use_fk_index_hint=False):
    """
    Pull from queryset in chunks. This is suitable for deep pagination, but
    cannot be used with ordered querysets (results will be sorted by the
    ``pagination_key`` fields, by default the pk).

    ``pagination_key`` is the tuple of field names to paginate by (the pk by
    default), and the order in which results will be yielded. Its fields must be
    jointly unique to guarantee that every matching result is returned -- e.g.
    ``('pk',)`` or ``('owner_id', 'pk')`` is okay, but just ``('owner_id',)`` is not.

    ``use_fk_index_hint``: when the leading pagination key is a foreign key's
    stored column (e.g. ``case_id`` backs the ``case`` FK), bound the parent's
    column each page so Postgres seeks the parent's index -- which it otherwise
    won't, since it won't carry the keyset's inequality across the join [1][2].
    Example: ``pagination_key=('case_id', 'pk'), use_fk_index_hint=True``.

    Retries on transient database connection failures (bounded at ~31
    minutes total) so long-running iterations survive brief outages.

    [1] https://postgrespro.com/list/thread-id/2550799
    [2] https://github.com/postgres/postgres/blob/REL_18_4/src/backend/optimizer/README
        (the EquivalenceClasses section, on how the planner propagates equalities across joins)
    """
    if queryset.ordered and not ignore_ordering:
        raise AssertionError("queryset_to_iterator does not respect ordering.  "
                             "Pass ignore_ordering=True to continue.")

    parent_column = _fk_index_column(model_cls, pagination_key) if use_fk_index_hint else None
    queryset = queryset.order_by(*pagination_key)
    last_doc_values = None
    while True:
        if last_doc_values is None:
            chunk_qs = queryset
        else:
            chunk_qs = queryset.filter(_lexicographic_greater_than(pagination_key, last_doc_values))
            if parent_column is not None:
                # The parent bound must be raw SQL: the ORM collapses
                # ``case__case_id`` to the child's own column, which Postgres can't
                # use to seek the parent. Safe: the column comes from model metadata
                # and the value is a bound parameter.
                chunk_qs = chunk_qs.extra(where=[f'{parent_column} >= %s'], params=[last_doc_values[0]])
        chunk = _fetch_chunk_with_retry(chunk_qs, limit, model_cls, last_doc_values)
        if not chunk:
            return
        for doc in chunk:
            yield doc

        last_doc_values = tuple(getattr(doc, key) for key in pagination_key)


def _fk_index_column(model_cls, pagination_key):
    """Return the parent column for the foreign key backing the leading pagination
    key, as a quoted ``"table"."column"`` SQL fragment (see ``queryset_to_iterator``).

    The leading key must be a foreign key's stored column (e.g. ``case_id`` backs
    the ``case`` FK). A foreign key with ``to_field`` guarantees the child's stored
    ``<fk>_id`` column equals the parent's ``to_field`` on every row, so a bound on
    the parent column is value-equivalent to the keyset's leading bound -- and,
    unlike the child column, one Postgres can seek the parent's index with.
    """
    leading_key = pagination_key[0]
    foreign_key = next(
        (f for f in model_cls._meta.fields if f.many_to_one and f.get_attname() == leading_key),
        None,
    )
    if foreign_key is None:
        raise ValueError(
            f"use_fk_index_hint requires pagination_key[0]={leading_key!r} to be a foreign "
            f"key's column on {model_cls.__name__}, but none is"
        )
    return f'"{foreign_key.related_model._meta.db_table}"."{foreign_key.target_field.column}"'


def _lexicographic_greater_than(fields, values):
    """Build the tuple comparison ``(a, b, ...) > (va, vb, ...)`` as a Q
    expression, expanding it to ``a > va OR (a = va AND b > vb) OR ...``.

    For a compound key it also ANDs a redundant ``a >= va`` on the leading
    field. It's implied by the comparison, but Postgres won't derive a bound
    from inside the OR [1], so the explicit ``>=`` is what lets it seek ``a``'s
    index instead of scanning from the start. This acts as a query planner hint:
    it makes a seek on ``a``'s index one of the options the planner can choose.

    [1] https://use-the-index-luke.com/sql/partial-results/fetch-next-page#sb-equivalent-logic
    """
    condition = Q()
    for index, (field, value) in enumerate(zip(fields, values)):
        ties = dict(zip(fields[:index], values[:index]))
        condition |= Q(**ties, **{f"{field}__gt": value})
    if len(fields) > 1:
        condition = Q(**{f"{fields[0]}__gte": values[0]}) & condition
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
