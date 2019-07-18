from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

import uuid
from collections import defaultdict

from django.db import OperationalError

try:
    from random import choices
except ImportError:
    from corehq.sql_db.backports import choices

from django.conf import settings
from django import db
from django.db.utils import InterfaceError as DjangoInterfaceError
from functools import wraps
from psycopg2._psycopg import InterfaceError as Psycopg2InterfaceError
import six
from memoized import memoized

from corehq.sql_db.config import partition_config
from corehq.util.quickcache import quickcache


ACCEPTABLE_STANDBY_DELAY_SECONDS = 3
STALE_CHECK_FREQUENCY = 30


def paginate_query_across_partitioned_databases(model_class, q_expression, annotate=None, query_size=5000,
                                                values=None):
    """
    Runs a query across all partitioned databases in small chunks and produces a generator
    with the results.

    :param model_class: A Django model class

    :param q_expression: An instance of django.db.models.Q representing the
    filter to apply

    :param annotate: (optional) If specified, should be a dictionary of annotated fields
    and their calculations. The dictionary will be splatted into the `.annotate` function

    :param values: (optional) If specified, should be a list of values to retrieve rather
    than retrieving entire objects.

    :return: A generator with the results
    """
    db_names = get_db_aliases_for_partitioned_query()
    for db_name in db_names:
        for row in paginate_query(db_name, model_class, q_expression, annotate, query_size, values):
            yield row


def paginate_query(db_name, model_class, q_expression, annotate=None, query_size=5000, values=None):
    """
    Runs a query on the given database in small chunks and produces a generator
    with the results.

    Iteration logic adopted from https://djangosnippets.org/snippets/1949/

    :param model_class: A Django model class

    :param q_expression: An instance of django.db.models.Q representing the
    filter to apply

    :param annotate: (optional) If specified, should be a dictionary of annotated fields
    and their calculations. The dictionary will be splatted into the `.annotate` function

    :param values: (optional) If specified, should be a list of values to retrieve rather
    than retrieving entire objects.

    :return: A generator with the results
    """
    sort_col = 'pk'

    return_values = None
    if values:
        return_values = [sort_col] + values

    qs = model_class.objects.using(db_name)
    if annotate:
        qs = qs.annotate(**annotate)

    qs = qs.filter(q_expression).order_by(sort_col)

    if return_values:
        qs = qs.values_list(*return_values)

    filter_expression = {}
    while True:
        results = qs.filter(**filter_expression)[:query_size]
        for row in results:
            if return_values:
                value = row[0]
                yield row[1:]
            else:
                value = row.pk
                yield row

        if len(results) < query_size:
            break

        filter_expression = {'{}__gt'.format(sort_col): value}


def split_list_by_db_partition(partition_values):
    """
    :param partition_values: Iterable of partition values (e.g. case IDs)
    :return: list of tuples (db_name, list(partition_values))
    """
    mapping = defaultdict(list)
    for value in partition_values:
        db_name = get_db_alias_for_partitioned_doc(value)
        mapping[db_name].append(value)
    return list(mapping.items())


def get_db_alias_for_partitioned_doc(partition_value):
    if settings.USE_PARTITIONED_DATABASE:
        from corehq.form_processor.backends.sql.dbaccessors import ShardAccessor
        db_name = ShardAccessor.get_database_for_doc(partition_value)
    else:
        db_name = 'default'
    return db_name


def get_db_aliases_for_partitioned_query():
    if settings.USE_PARTITIONED_DATABASE:
        db_names = partition_config.get_form_processing_dbs()
    else:
        db_names = ['default']
    return db_names


def get_default_db_aliases():
    return ['default']


def get_all_db_aliases():
    return list(settings.DATABASES)


def get_default_and_partitioned_db_aliases():
    return list(set(get_db_aliases_for_partitioned_query() + get_default_db_aliases()))


def new_id_in_same_dbalias(partition_value):
    """
    Returns a new partition value that belongs to the same db alias as
        the given partition value does
    """
    old_db_name = get_db_alias_for_partitioned_doc(partition_value)
    new_db_name = None
    while old_db_name != new_db_name:
        # todo; guard against infinite recursion
        new_partition_value = six.text_type(uuid.uuid4())
        new_db_name = get_db_alias_for_partitioned_doc(new_partition_value)
    return new_partition_value


def handle_connection_failure(get_db_aliases=get_default_db_aliases):
    def _inner2(fn):
        @wraps(fn)
        def _inner(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except db.utils.DatabaseError:
                # we have to do this manually to avoid issues with
                # open transactions and already closed connections
                for db_name in get_db_aliases():
                    db.transaction.rollback(using=db_name)

                # re raise the exception for additional error handling
                raise
            except (Psycopg2InterfaceError, DjangoInterfaceError):
                # force closing the connection to prevent Django from trying to reuse it.
                # http://www.tryolabs.com/Blog/2014/02/12/long-time-running-process-and-django-orm/
                for db_name in get_db_aliases():
                    db.connections[db_name].close()

                # re raise the exception for additional error handling
                raise

        return _inner

    return _inner2


def get_all_sharded_models():
    from corehq.sql_db.models import PartitionedModel
    for subclass in _get_all_nested_subclasses(PartitionedModel):
        if not subclass._meta.abstract:
            yield subclass


def _get_all_nested_subclasses(cls):
    seen = set()
    for subclass in cls.__subclasses__():
        for sub_subclass in _get_all_nested_subclasses(subclass):
            # in case of multiple inheritance
            if sub_subclass not in seen:
                seen.add(sub_subclass)
                yield sub_subclass
        if subclass not in seen:
            seen.add(subclass)
            yield subclass


@memoized
def get_standby_databases(relevant_dbs=None):
    standby_dbs = []
    for db_alias in settings.DATABASES:
        if relevant_dbs is None or db_alias in relevant_dbs:
            with db.connections[db_alias].cursor() as cursor:
                cursor.execute("SELECT pg_is_in_recovery()")
                [(is_standby, )] = cursor.fetchall()
                if is_standby:
                    standby_dbs.append(db_alias)
    return standby_dbs


def get_replication_delay_for_standby(db_alias, relevant_dbs=None):
    """
    Finds the replication delay for given database by running a SQL query on standby database.
        See https://www.postgresql.org/message-id/CADKbJJWz9M0swPT3oqe8f9+tfD4-F54uE6Xtkh4nERpVsQnjnw@mail.gmail.com

    If the given database is not a standby database, zero delay is returned
    If standby process (wal_receiver) is not running on standby a `VERY_LARGE_DELAY` is returned
    """

    if db_alias not in get_standby_databases(relevant_dbs):
        return 0
    # used to indicate that the wal_receiver process on standby is not running
    VERY_LARGE_DELAY = 100000
    try:
        sql = """
        SELECT
        CASE
            WHEN NOT EXISTS (SELECT 1 FROM pg_stat_wal_receiver) THEN %(delay)s
            WHEN pg_last_xlog_receive_location() = pg_last_xlog_replay_location() THEN 0
            ELSE EXTRACT (EPOCH FROM now() - pg_last_xact_replay_timestamp())::INTEGER
        END
        AS replication_lag;
        """
        with db.connections[db_alias].cursor() as cursor:
            cursor.execute(sql, {'delay': VERY_LARGE_DELAY})
            [(delay, )] = cursor.fetchall()
            return delay
    except OperationalError:
        return VERY_LARGE_DELAY


@memoized
def get_standby_delays_by_db():
    ret = {}
    for _db, config in six.iteritems(settings.DATABASES):
        delay = config.get('HQ_ACCEPTABLE_STANDBY_DELAY')
        if delay:
            ret[_db] = delay
    return ret


@quickcache(['dbs'], timeout=STALE_CHECK_FREQUENCY, skip_arg=lambda *args: settings.UNIT_TESTING)
def filter_out_stale_standbys(dbs):
    # from given list of databases filters out those with more than
    #   acceptable standby delay, if that database is a standby
    delays_by_db = get_standby_delays_by_db()
    relevant_dbs = tuple(dbs)
    return [
        db
        for db in dbs
        if get_replication_delay_for_standby(db, relevant_dbs) <= delays_by_db.get(db, ACCEPTABLE_STANDBY_DELAY_SECONDS)
    ]


def select_db_for_read(weighted_dbs):
    """
    Returns a randomly selected database per the weights assigned from
        a list of databases. If any database is standby and its replication has
        more than acceptable delay, that db is dropped from selection

    Args:
        weighted_dbs: a list of tuple of db and the weight.
            [
                ("pgmain", 5),
                ("pgmainstandby", 5)
            ]

    """
    # convert to a db to weight dictionary
    weights_by_db = {_db: weight for _db, weight in weighted_dbs}

    # filter out stale standby dbs
    fresh_dbs = filter_out_stale_standbys(list(weights_by_db.keys()))
    dbs = []
    weights = []
    for _db, weight in six.iteritems(weights_by_db):
        if _db in fresh_dbs:
            dbs.append(_db)
            weights.append(weight)

    if dbs:
        return choices(dbs, weights=weights)[0]
