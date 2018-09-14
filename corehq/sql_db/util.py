from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
import uuid
from collections import defaultdict
from numpy import random

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


def run_query_across_partitioned_databases(model_class, q_expression, values=None, annotate=None):
    """
    Runs a query across all partitioned databases and produces a generator
    with the results.

    :param model_class: A Django model class

    :param q_expression: An instance of django.db.models.Q representing the
    filter to apply

    :param values: (optional) If specified, should be a list of values to retrieve rather
    than retrieving entire objects. If a list with a single value is given, the result will
    be a generator of single values. If a list with multiple values is given, the result
    will be a generator of tuples.

    :param annotate: (optional) If specified, should by a dictionary of annotated fields
    and their calculations. The dictionary will be splatted into the `.annotate` function

    :return: A generator with the results
    """
    db_names = get_db_aliases_for_partitioned_query()

    if values and not isinstance(values, (list, tuple)):
        raise ValueError("Expected a list or tuple")

    for db_name in db_names:
        qs = model_class.objects.using(db_name)
        if annotate:
            qs = qs.annotate(**annotate)

        qs = qs.filter(q_expression)
        if values:
            if len(values) == 1:
                qs = qs.values_list(*values, flat=True)
            else:
                qs = qs.values_list(*values)

        for result in qs.iterator():
            yield result


def paginate_query_across_partitioned_databases(model_class, q_expression, annotate=None, query_size=5000):
    """
    Runs a query across all partitioned databases in small chunks and produces a generator
    with the results.

    Iteration logic adopted from https://djangosnippets.org/snippets/1949/

    :param model_class: A Django model class

    :param q_expression: An instance of django.db.models.Q representing the
    filter to apply

    :param annotate: (optional) If specified, should by a dictionary of annotated fields
    and their calculations. The dictionary will be splatted into the `.annotate` function

    :return: A generator with the results
    """
    db_names = get_db_aliases_for_partitioned_query()

    for db_name in db_names:
        qs = model_class.objects.using(db_name)
        if annotate:
            qs = qs.annotate(**annotate)

        qs = qs.filter(q_expression)
        sort_col = 'pk'
        value = 0
        last_value = qs.order_by('-{}'.format(sort_col)).values_list(sort_col, flat=True).first()
        if last_value is not None:
            qs = qs.order_by(sort_col)
            while value < last_value:
                filter_expression = {'{}__gt'.format(sort_col): value}
                for row in qs.filter(**filter_expression)[:query_size]:
                    value = row.pk
                    yield row


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
def get_standby_databases():
    standby_dbs = []
    for db_alias in settings.DATABASES:
        with db.connections[db_alias].cursor() as cursor:
            cursor.execute("SELECT pg_is_in_recovery()")
            [(is_standby, )] = cursor.fetchall()
            if is_standby:
                standby_dbs.append(db_alias)
    return standby_dbs


def get_replication_delay_for_standby(db_alias):
    """
    Finds the replication delay for given database by running a SQL query on standby database.
        See https://www.postgresql.org/message-id/CADKbJJWz9M0swPT3oqe8f9+tfD4-F54uE6Xtkh4nERpVsQnjnw@mail.gmail.com

    If the given database is not a standby database, zero delay is returned
    If standby process (wal_receiver) is not running on standby a `VERY_LARGE_DELAY` is returned
    """
    if db_alias not in get_standby_databases():
        return 0
    # used to indicate that the wal_receiver process on standby is not running
    VERY_LARGE_DELAY = 100000
    sql = """
    SELECT
    CASE
        WHEN NOT EXISTS (SELECT 1 FROM pg_stat_wal_receiver) THEN {delay}
        WHEN pg_last_xlog_receive_location() = pg_last_xlog_replay_location() THEN 0
        ELSE EXTRACT (EPOCH FROM now() - pg_last_xact_replay_timestamp())::INTEGER
    END
    AS replication_lag;
    """.format(delay=VERY_LARGE_DELAY)
    with db.connections[db_alias].cursor() as cursor:
        cursor.execute(sql)
        [(delay, )] = cursor.fetchall()
        return delay


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
    return [
        db
        for db in dbs
        if get_replication_delay_for_standby(db) <= delays_by_db.get(db, ACCEPTABLE_STANDBY_DELAY_SECONDS)
    ]


def select_db_for_read(weighted_dbs):
    """
    Returns a randomly selected database per the weights assigned from
        a list of databases. If any database is standby and its replication has
        more than accesptable delay, that db is dropped from selection

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
    fresh_dbs = filter_out_stale_standbys(weights_by_db)
    dbs = []
    weights = []
    for _db, weight in six.iteritems(weights_by_db):
        if _db in fresh_dbs:
            dbs.append(_db)
            weights.append(weight)

    if dbs:
        # normalize weights of remaining dbs
        total_weight = sum(weights)
        normalized_weights = [float(weight) / total_weight for weight in weights]
        return random.choice(dbs, p=normalized_weights)
